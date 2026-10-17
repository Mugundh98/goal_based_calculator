"""API tests for the assistant: sessions, the streamed function-calling loop and its guardrails.

A scripted FakeLLM replaces Gemini; tools run against the real test database.
"""

import json
from contextlib import nullcontext
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.api.routes.chat import get_llm, get_session_factory
from app.chatbot import rag, tools
from app.chatbot.llm import LLMError
from app.chatbot.orchestrator import MAX_ROUNDS, STOPPED
from app.core.config import get_settings
from app.main import app
from app.models import ChatMessage, Fund, FundMetrics, Goal, KbChunk, KbDocument, ToolCall
from tests.chat_fakes import FakeLLM, call, say
from tests.conftest import login_headers

THIS_YEAR = date.today().year


@pytest.fixture
def llm(db):
    """Install a FakeLLM (script it per test) and let the stream use the test session."""
    fake = FakeLLM()
    app.dependency_overrides[get_llm] = lambda: fake
    app.dependency_overrides[get_session_factory] = lambda: lambda: nullcontext(db)
    yield fake


def new_session(client, headers):
    response = client.post("/api/chat/sessions", headers=headers)
    assert response.status_code == 201
    return response.json()["id"]


def ask(client, headers, session_id, text, expect=200):
    response = client.post(
        f"/api/chat/sessions/{session_id}/messages", json={"text": text}, headers=headers
    )
    assert response.status_code == expect, response.text
    if expect != 200:
        return response.json()
    assert response.headers["content-type"].startswith("text/event-stream")
    events = []
    for block in response.text.strip().split("\n\n"):
        name, data = block.split("\n", 1)
        events.append((name.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return events


def answer_of(events):
    return events[-1][1]["message"]


def make_goal(client, headers, **overrides):
    body = {"goal_type": "education", "name": "College", "target_amount": 2_000_000,
            "target_year": THIS_YEAR + 10, "monthly_sip": 10_000} | overrides  # fmt: skip
    response = client.post("/api/goals", json=body, headers=headers)
    assert response.status_code == 201
    return response.json()["id"]


# --- Status and sessions ---------------------------------------------------------------------


def test_status_reports_whether_the_assistant_is_configured(client, auth_headers, db):
    app.dependency_overrides[get_llm] = lambda: None
    body = client.get("/api/chat/status", headers=auth_headers).json()
    assert body["enabled"] is False and body["model"] is None
    session_id = new_session(client, auth_headers)
    assert ask(client, auth_headers, session_id, "hi", expect=503)["detail"]

    app.dependency_overrides[get_llm] = lambda: FakeLLM()
    assert client.get("/api/chat/status", headers=auth_headers).json()["model"] == "fake-chat"


def test_sessions_are_private(client, auth_headers, llm):
    assert client.get("/api/chat/sessions").status_code == 401
    mine = new_session(client, auth_headers)
    other = login_headers(client, "other@example.com")
    assert client.get(f"/api/chat/sessions/{mine}", headers=other).status_code == 404
    assert ask(client, other, mine, "hi", expect=404)
    assert client.delete(f"/api/chat/sessions/{mine}", headers=other).status_code == 404
    assert client.get("/api/chat/sessions", headers=other).json() == []
    assert client.delete(f"/api/chat/sessions/{mine}", headers=auth_headers).status_code == 204
    assert client.get("/api/chat/sessions", headers=auth_headers).json() == []


def test_message_length_is_limited(client, auth_headers, llm):
    session_id = new_session(client, auth_headers)
    ask(client, auth_headers, session_id, "   ", expect=422)
    ask(client, auth_headers, session_id, "x" * 2001, expect=422)


# --- The loop --------------------------------------------------------------------------------


def test_plain_answer_is_streamed_and_stored(client, auth_headers, llm):
    llm.script = [say("I can help with goals, funds and your portfolio.")]
    session_id = new_session(client, auth_headers)
    events = ask(client, auth_headers, session_id, "What can you do?")
    assert [name for name, _ in events] == ["text", "text", "done"]
    assert "".join(d["text"] for n, d in events if n == "text") == answer_of(events)["content"]
    detail = client.get(f"/api/chat/sessions/{session_id}", headers=auth_headers).json()
    assert detail["title"] == "What can you do?"
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
    assert detail["messages"][1]["tools"] == [] and detail["messages"][1]["error"] is None


def test_tool_calls_run_for_this_user_and_are_audited(client, db, auth_headers, llm):
    goal_id = make_goal(client, auth_headers)
    make_goal(client, login_headers(client, "other@example.com"), name="Not mine")
    llm.script = [call("list_goals"), say("You have one goal, College, due in 10 years.")]
    session_id = new_session(client, auth_headers)
    events = ask(client, auth_headers, session_id, "What goals do I have?")
    assert [n for n, _ in events] == ["tool", "tool", "text", "text", "done"]
    assert events[0][1] == {"name": "list_goals", "status": "running"}
    assert events[1][1]["status"] == "ok" and events[1][1]["ms"] >= 0

    [results] = llm.conversations[0].results
    goals = results[0].data["goals"]
    assert [g["goal_id"] for g in goals] == [goal_id]  # only the user's own goals
    logged = db.scalar(select(ToolCall))
    assert (logged.tool, logged.status, logged.arguments) == ("list_goals", "ok", {})
    assert logged.result["goals"][0]["name"] == "College"
    assert answer_of(events)["tools"][0]["tool"] == "list_goals"


def test_bad_arguments_and_unknown_tools_go_back_to_the_model(client, auth_headers, llm):
    llm.script = [
        call("run_simulation", goal_id="abc"),
        call("delete_everything"),
        call("run_simulation", goal_id=999_999),
        say("Sorry, I could not find that goal."),
    ]
    session_id = new_session(client, auth_headers)
    events = ask(client, auth_headers, session_id, "simulate")
    statuses = [d["status"] for n, d in events if n == "tool" and d["status"] != "running"]
    assert statuses == ["error", "error", "error"]
    errors = [r[0].data["error"] for r in llm.conversations[0].results]
    assert errors[0].startswith("Invalid goal_id")
    assert "Unknown tool" in errors[1]
    assert "list_goals" in errors[2]  # tells the model how to recover
    assert answer_of(events)["content"] == "Sorry, I could not find that goal."


def test_goal_is_saved_only_after_the_user_confirms(client, db, auth_headers, llm):
    details = {"goal_type": "travel", "name": "Japan trip", "target_amount": 400_000,
               "target_year": THIS_YEAR + 3, "monthly_sip": 8000}  # fmt: skip
    llm.script = [
        call("create_goal", **details, confirmed=True),  # the model tries to skip the preview
        say("Here is the preview. Shall I save it?"),
        call("create_goal", **details, confirmed=True),
        say("Saved."),
    ]
    session_id = new_session(client, auth_headers)
    ask(client, auth_headers, session_id, "Plan a trip to Japan")
    first = llm.conversations[0].results[0][0].data
    assert first["saved"] is False and first["needs_confirmation"] is True
    assert first["projection"]["inflated_target"] > 400_000
    assert db.scalar(select(func.count()).select_from(Goal)) == 0

    ask(client, auth_headers, session_id, "Yes, save it")
    second = llm.conversations[1].results[0][0].data
    assert second["saved"] is True
    goal = db.get(Goal, second["goal_id"])
    assert (goal.name, goal.goal_type, goal.monthly_sip) == ("Japan trip", "travel", Decimal(8000))


def test_charts_go_to_the_browser_not_the_model(client, db, auth_headers, llm):
    ids = []
    for k, (ret, vol) in enumerate([(14.0, 16.0), (12.0, 13.0)]):
        fund = Fund(scheme_code=970_000 + k, name=f"Fund {k}", amc=f"AMC {k}",
                    scheme_type="Open Ended", category="Mid Cap Fund", asset_class="equity",
                    plan="direct", option="growth")  # fmt: skip
        db.add(fund)
        db.flush()
        db.add(FundMetrics(fund_id=fund.id, as_of_date=date(2026, 10, 15),
                           history_start=date(2015, 1, 1), return_3y=ret, volatility=vol,
                           sharpe=0.5, risk_free_rate=6.0,
                           computed_at=datetime(2026, 1, 1, tzinfo=UTC)))  # fmt: skip
        ids.append(fund.id)
    db.commit()
    llm.script = [call("compare_funds", fund_ids=ids), say("Fund 0 returned more, with more risk.")]
    session_id = new_session(client, auth_headers)
    events = ask(client, auth_headers, session_id, "compare")
    [chart] = [d["chart"] for n, d in events if n == "chart"]
    assert chart["type"] == "fund_table" and [f["return_3y"] for f in chart["funds"]] == [
        14.0,
        12.0,
    ]
    assert answer_of(events)["charts"] == [chart]  # kept with the stored answer
    shown = llm.conversations[0].results[0][0].data
    assert "type" not in shown  # the model sees the data only


def test_explanations_come_from_the_knowledge_base(client, db, auth_headers, llm, monkeypatch):
    monkeypatch.setattr(tools, "RELEVANT_SIMILARITY", 0.1)  # bag-of-words fake embeddings
    llm.script = [call("explain_term", question="What is an expense ratio and why does it matter?"),
                  say("The expense ratio is a yearly cost (Costs of investing).")]  # fmt: skip
    session_id = new_session(client, auth_headers)
    ask(client, auth_headers, session_id, "What is an expense ratio?")
    assert db.scalar(select(func.count()).select_from(KbDocument)) == 20  # built on first use
    passages = llm.conversations[0].results[0][0].data["passages"]
    assert passages and "xpense ratio" in passages[0]["source"]


def test_off_topic_questions_find_no_passages(client, db, auth_headers, llm):
    rag.ingest(db, llm)
    llm.script = [call("explain_term", question="capital city of a European country"),
                  say("I can only help with personal finance.")]  # fmt: skip
    session_id = new_session(client, auth_headers)
    ask(client, auth_headers, session_id, "What is the capital of France?")
    result = llm.conversations[0].results[0][0].data
    assert result["passages"] == [] and result["note"].startswith("Nothing in the knowledge base")


def test_ingest_is_idempotent_and_follows_changes(db, tmp_path):
    fake = FakeLLM()
    for name, body in (("a", "Alpha"), ("b", "Beta")):
        (tmp_path / f"{name}.md").write_text(f"# {body}\n\n## One\n\n{body} text.\n", "utf-8")
    report = rag.ingest(db, fake, rag.load_articles(tmp_path))
    assert (report.added, report.chunks) == (2, 2)
    embedded = len(fake.embedded)
    assert rag.ingest(db, fake, rag.load_articles(tmp_path)).unchanged == 2
    assert len(fake.embedded) == embedded  # nothing re-embedded

    (tmp_path / "a.md").write_text("# Alpha\n\n## One\n\nNew text.\n\n## Two\n\nMore.\n", "utf-8")
    (tmp_path / "b.md").unlink()
    report = rag.ingest(db, fake, rag.load_articles(tmp_path))
    assert (report.updated, report.removed, report.chunks) == (1, 1, 2)
    assert db.scalar(select(func.count()).select_from(KbChunk)) == 2
    [passage] = rag.search(db, fake, "more", k=1)
    assert passage.heading == "Two" and passage.similarity > 0.5  # closest by cosine


# --- Guardrails ------------------------------------------------------------------------------


def test_no_personal_identifiers_reach_the_model(client, auth_headers, llm):
    client.put("/api/profile", headers=auth_headers, json={
        "date_of_birth": "1990-05-17", "employment_type": "salaried", "monthly_income": 150000,
        "monthly_expenses": 60000, "monthly_emi": 10000, "current_savings": 300000,
        "existing_investments": 0, "dependents": 2,
    })  # fmt: skip
    llm.script = [call("get_risk_profile"), say("Your surplus is ₹80,000 a month.")]
    session_id = new_session(client, auth_headers)
    events = ask(client, auth_headers, session_id, "How much can I invest?")
    conversation = llm.conversations[0]
    sent = json.dumps([conversation.system, conversation.sent,
                       [r.data for rs in conversation.results for r in rs]])  # fmt: skip
    for identifier in ("user@example.com", "Test User", "1990-05-17"):
        assert identifier not in sent
    profile = conversation.results[0][0].data
    assert profile["monthly_surplus"] == 80_000 and profile["age"] >= 30
    assert answer_of(events)["ungrounded"] == []


def test_invented_numbers_are_recorded(client, auth_headers, llm):
    make_goal(client, auth_headers)
    llm.script = [call("list_goals"), say("You need ₹1,23,456 more, so ₹9,87,654 in all.")]
    session_id = new_session(client, auth_headers)
    message = answer_of(ask(client, auth_headers, session_id, "Am I on track?"))
    assert message["ungrounded"] == ["1,23,456", "9,87,654"]


def test_model_failure_gives_a_fallback_answer(client, auth_headers, llm):
    llm.script = [LLMError("rate_limit", "429 quota")]
    session_id = new_session(client, auth_headers)
    events = ask(client, auth_headers, session_id, "Hello")
    assert [n for n, _ in events] == ["error", "done"]
    message = answer_of(events)
    assert message["error"] == "rate_limit" and "try again" in message["content"]

    llm.script = [say("Hello again.")]
    ask(client, auth_headers, session_id, "Hello?")
    history = llm.conversations[1].history
    assert [(m.role, m.text) for m in history] == [("user", "Hello")]  # fallback left out


def test_history_is_sent_with_each_question(client, auth_headers, llm):
    llm.script = [say("Ten years is a long horizon."), say("Then equity suits it.")]
    session_id = new_session(client, auth_headers)
    ask(client, auth_headers, session_id, "My goal is ten years away.")
    ask(client, auth_headers, session_id, "What should I invest in?")
    history = llm.conversations[1].history
    assert [m.role for m in history] == ["user", "assistant"]
    assert history[1].text == "Ten years is a long horizon."


def test_the_loop_stops_after_too_many_rounds(client, db, auth_headers, llm):
    llm.script = [call("list_goals") for _ in range(MAX_ROUNDS + 1)]
    session_id = new_session(client, auth_headers)
    message = answer_of(ask(client, auth_headers, session_id, "loop"))
    assert message["content"] == STOPPED
    assert db.scalar(select(func.count()).select_from(ToolCall)) == MAX_ROUNDS


def test_questions_are_rate_limited(client, db, auth_headers, llm, monkeypatch):
    monkeypatch.setattr(get_settings(), "chat_messages_per_hour", 2)
    llm.script = [say("one"), say("two")]
    session_id = new_session(client, auth_headers)
    ask(client, auth_headers, session_id, "1")
    ask(client, auth_headers, session_id, "2")
    body = ask(client, auth_headers, session_id, "3", expect=429)
    assert "2 questions an hour" in body["detail"]
    assert db.scalar(select(func.count()).where(ChatMessage.role == "user")) == 2
