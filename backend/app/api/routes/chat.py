"""Assistant endpoints. Answers stream as server-sent events (text/event-stream)."""

import json
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, DbSession
from app.chatbot.llm import LLM, default_llm
from app.chatbot.orchestrator import run_turn
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import ChatMessage, ChatSession, User
from app.schemas.chat import ChatStatus, MessageIn, SessionDetail, SessionSummary
from app.services import chat as service

router = APIRouter(prefix="/chat", tags=["assistant"])


def get_llm() -> LLM | None:
    """The language model; overridden with a scripted fake in the tests."""
    return default_llm()


SessionFactory = Callable[[], AbstractContextManager[Session]]


def get_session_factory() -> SessionFactory:
    """The stream opens its own database session: it outlives the request's dependencies."""
    return SessionLocal


Llm = Annotated[LLM | None, Depends(get_llm)]


def _owned(db: Session, user: User, session_id: int) -> ChatSession:
    session = service.get_session(db, user, session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return session


@router.get("/status", response_model=ChatStatus)
def chat_status(user: CurrentUser, db: DbSession, llm: Llm) -> ChatStatus:
    documents, chunks = service.knowledge_counts(db)
    return ChatStatus(
        enabled=llm is not None,
        model=llm.chat_model if llm else None,
        knowledge_documents=documents,
        knowledge_chunks=chunks,
    )


@router.get("/sessions", response_model=list[SessionSummary])
def sessions(user: CurrentUser, db: DbSession) -> list[SessionSummary]:
    return [service.summary(s) for s in service.list_sessions(db, user)]


@router.post("/sessions", response_model=SessionSummary, status_code=status.HTTP_201_CREATED)
def new_session(user: CurrentUser, db: DbSession) -> SessionSummary:
    return service.summary(service.create_session(db, user))


@router.get("/sessions/{session_id}", response_model=SessionDetail)
def read_session(session_id: int, user: CurrentUser, db: DbSession) -> SessionDetail:
    return service.detail(db, _owned(db, user, session_id))


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_session(session_id: int, user: CurrentUser, db: DbSession) -> None:
    service.delete_session(db, _owned(db, user, session_id))


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@router.post("/sessions/{session_id}/messages")
def ask(
    session_id: int,
    body: MessageIn,
    user: CurrentUser,
    db: DbSession,
    llm: Llm,
    factory: Annotated[SessionFactory, Depends(get_session_factory)],
) -> StreamingResponse:
    """Ask a question. Events: `text` (a piece of the answer), `tool` (running / ok / error),
    `chart`, `error` (fallback message), and `done` with the stored answer."""
    _owned(db, user, session_id)
    if llm is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail="The assistant is not configured"
        )
    limit = get_settings().chat_messages_per_hour
    if service.rate_limited(db, user, limit):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"You can ask {limit} questions an hour. Please try again later.",
        )
    user_id, text = user.id, body.text

    def events() -> Iterator[str]:
        with factory() as stream_db:
            stream_user = stream_db.get(User, user_id)
            session = stream_db.get(ChatSession, session_id)
            assert stream_user is not None and session is not None
            for event in run_turn(stream_db, stream_user, session, text, llm):
                if event.type == "done":
                    message = stream_db.get(ChatMessage, event.data["message_id"])
                    assert message is not None
                    yield _sse("done", {"message": service.message_out(message).model_dump()})
                else:
                    yield _sse(event.type, event.data)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        # No caching or proxy buffering: each piece must reach the browser at once.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
