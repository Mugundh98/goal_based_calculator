"""Chat sessions and messages: listing, ownership, the per-user rate limit, API shapes."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import ChatMessage, ChatSession, KbChunk, KbDocument, User
from app.schemas.chat import MessageOut, SessionDetail, SessionSummary, ToolCallOut


def list_sessions(db: Session, user: User) -> list[ChatSession]:
    """Most recently used first."""
    return list(
        db.scalars(
            select(ChatSession)
            .where(ChatSession.user_id == user.id)
            .order_by(ChatSession.updated_at.desc(), ChatSession.id.desc())
        )
    )


def create_session(db: Session, user: User) -> ChatSession:
    session = ChatSession(user_id=user.id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session(db: Session, user: User, session_id: int) -> ChatSession | None:
    """None for a missing session and for another user's (the caller answers 404)."""
    return db.scalar(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user.id)
    )


def delete_session(db: Session, session: ChatSession) -> None:
    db.delete(session)
    db.commit()


def questions_since(db: Session, user: User, since: datetime) -> int:
    """How many questions the user has asked since `since` (for the rate limit)."""
    return (
        db.scalar(
            select(func.count())
            .select_from(ChatMessage)
            .join(ChatSession, ChatSession.id == ChatMessage.session_id)
            .where(
                ChatSession.user_id == user.id,
                ChatMessage.role == "user",
                ChatMessage.created_at >= since,
            )
        )
        or 0
    )


def rate_limited(db: Session, user: User, per_hour: int) -> bool:
    return questions_since(db, user, datetime.now(UTC) - timedelta(hours=1)) >= per_hour


def knowledge_counts(db: Session) -> tuple[int, int]:
    documents = db.scalar(select(func.count()).select_from(KbDocument)) or 0
    chunks = db.scalar(select(func.count()).select_from(KbChunk)) or 0
    return documents, chunks


def message_out(message: ChatMessage) -> MessageOut:
    payload = message.payload or {}
    return MessageOut(
        id=message.id,
        role=message.role,
        content=message.content,
        created_at=message.created_at,
        charts=payload.get("charts", []),
        tools=[
            ToolCallOut(
                tool=c.tool, arguments=c.arguments, status=c.status, latency_ms=c.latency_ms
            )
            for c in message.tool_calls
        ],
        ungrounded=payload.get("ungrounded", []),
        error=payload.get("error"),
    )


def summary(session: ChatSession) -> SessionSummary:
    return SessionSummary(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def detail(db: Session, session: ChatSession) -> SessionDetail:
    messages = db.scalars(
        select(ChatMessage)
        .options(selectinload(ChatMessage.tool_calls))
        .where(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.id)
    ).all()
    return SessionDetail(
        **summary(session).model_dump(), messages=[message_out(m) for m in messages]
    )
