"""The function-calling loop for one question.

user message -> model (with tool declarations) -> tool calls? -> run each tool for this user,
log it -> results back to the model -> ... -> final answer (streamed) -> grounding check ->
stored. Yields events for the browser (server-sent events): text pieces, tool activity,
charts, and finally the stored message.
"""

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.chatbot import grounding
from app.chatbot.llm import LLM, HistoryMessage, LLMError, ToolResult
from app.chatbot.prompts import system_prompt
from app.chatbot.tools import TOOLS, ToolContext, execute
from app.models import ChatMessage, ChatSession, ToolCall, User

logger = logging.getLogger(__name__)

HISTORY_MESSAGES = 12  # earlier messages sent with each question (6 exchanges)
HISTORY_CHARS = 4000  # per message
MAX_ROUNDS = 6  # model <-> tools round trips per question
MAX_CALLS_PER_ROUND = 5
TITLE_CHARS = 60

FALLBACK = {
    "rate_limit": "The assistant is getting too many requests right now. Please try again in "
    "a minute; everything else in GoalWise works as usual.",
    "unavailable": "The assistant could not reach the language model just now. Please try "
    "again shortly; your goals, simulations and portfolio pages still work.",
    "config": "The assistant is not set up correctly (the API key was refused). Please tell "
    "the administrator.",
}
STOPPED = "I stopped after several steps without a final answer. Please ask a narrower question."


@dataclass(frozen=True)
class Event:
    type: str  # text | tool | chart | done | error
    data: dict[str, Any]


def history(db: Session, session: ChatSession, before_id: int | None = None) -> list[ChatMessage]:
    query = select(ChatMessage).where(ChatMessage.session_id == session.id)
    if before_id is not None:
        query = query.where(ChatMessage.id < before_id)
    recent = db.scalars(query.order_by(ChatMessage.id.desc()).limit(HISTORY_MESSAGES)).all()
    return list(reversed(recent))


def _awaiting_confirmation(messages: list[ChatMessage]) -> set[str]:
    """Tools whose result in the last answer asked the user to confirm."""
    for message in reversed(messages):
        if message.role == "assistant":
            return {
                c.tool for c in message.tool_calls if c.result.get("needs_confirmation") is True
            }
    return set()


def run_turn(
    db: Session,
    user: User,
    session: ChatSession,
    text: str,
    llm: LLM,
    today: date | None = None,
) -> Iterator[Event]:
    earlier = history(db, session)
    question = ChatMessage(session_id=session.id, role="user", content=text)
    db.add(question)
    if session.title == "New chat":
        session.title = text[:TITLE_CHARS].strip() + ("…" if len(text) > TITLE_CHARS else "")
    session.updated_at = func.now()  # most recently used conversations first
    answer = ChatMessage(session_id=session.id, role="assistant", content="", payload={})
    db.add(answer)
    db.commit()  # the question is kept even if the model fails

    prompt = system_prompt(today)
    context = ToolContext(db, user, llm, today, _awaiting_confirmation(earlier))
    past = [
        HistoryMessage("user" if m.role == "user" else "assistant", m.content[:HISTORY_CHARS])
        for m in earlier
        if m.content and not m.payload.get("error")
    ]
    conversation = llm.conversation(prompt, past, [t.spec for t in TOOLS.values()])
    pieces: list[str] = []
    charts: list[dict[str, Any]] = []
    sources: list[Any] = [prompt, text, *(m.content for m in earlier)]
    error: str | None = None
    try:
        stream = conversation.send(text)
        for round_number in range(MAX_ROUNDS + 1):
            calls = []
            for chunk in stream:
                if chunk.text:
                    pieces.append(chunk.text)
                    yield Event("text", {"text": chunk.text})
                calls.extend(chunk.calls)
            if not calls:
                break
            if round_number == MAX_ROUNDS:
                pieces.append(("\n\n" if pieces else "") + STOPPED)
                yield Event("text", {"text": STOPPED})
                break
            results = []
            for call in calls[:MAX_CALLS_PER_ROUND]:
                yield Event("tool", {"name": call.name, "status": "running"})
                done = execute(context, call.name, call.args)
                db.add(
                    ToolCall(
                        message_id=answer.id,
                        tool=call.name,
                        arguments=call.args,
                        result=done.data,
                        status=done.status,
                        latency_ms=done.latency_ms,
                    )
                )
                db.commit()
                sources.append(done.data)
                if done.chart:
                    charts.append(done.chart)
                    yield Event("chart", {"chart": done.chart})
                yield Event(
                    "tool", {"name": call.name, "status": done.status, "ms": done.latency_ms}
                )
                results.append(ToolResult(call, done.data))
            stream = conversation.send_tool_results(results)
    except LLMError as exc:
        logger.warning("Assistant unavailable (%s): %s", exc.kind, exc)
        error = exc.kind
        notice = FALLBACK[exc.kind]
        pieces.append(("\n\n" if pieces else "") + notice)
        yield Event("error", {"kind": exc.kind, "message": notice})
    except GeneratorExit:  # the browser went away mid-answer: keep what was said so far
        answer.content = "".join(pieces).strip() or "(The answer was interrupted.)"
        answer.payload = {"charts": charts, "model": conversation.model, "interrupted": True}
        db.commit()
        raise

    content = "".join(pieces).strip() or "Sorry, I could not produce an answer."
    answer.content = content
    answer.payload = {
        "charts": charts,
        "model": conversation.model,
        "ungrounded": [] if error else grounding.ungrounded(content, sources),
        **({"error": error} if error else {}),
    }
    db.commit()
    db.refresh(answer)
    yield Event("done", {"message_id": answer.id})
