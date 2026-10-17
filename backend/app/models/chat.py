"""Conversational assistant (Phase 10): chat history, the tool-call audit trail, knowledge base."""

from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

EMBEDDING_DIMENSIONS = 768


class ChatSession(Base):
    """One conversation of one user."""

    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(80), server_default="New chat")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.id"
    )


class ChatMessage(Base):
    """A user question or an assistant answer. Answers carry charts and the grounding check."""

    __tablename__ = "chat_messages"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="ck_chat_messages_role"),
        # The rate limit counts a user's recent questions; history reads a session in order.
        Index("ix_chat_messages_session_id", "session_id", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(10))
    content: Mapped[str] = mapped_column(Text)
    # Assistant only: charts for the UI, the model used, numbers not found in any tool result,
    # and whether the answer is a fallback after an error.
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped[ChatSession] = relationship(back_populates="messages")
    tool_calls: Mapped[list["ToolCall"]] = relationship(
        back_populates="message", cascade="all, delete-orphan", order_by="ToolCall.id"
    )


class ToolCall(Base):
    """Audit trail: every function the model asked for, with what it was given and returned."""

    __tablename__ = "tool_calls"
    __table_args__ = (CheckConstraint("status IN ('ok', 'error')", name="ck_tool_calls_status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[int] = mapped_column(
        ForeignKey("chat_messages.id", ondelete="CASCADE"), index=True
    )  # the assistant answer it served
    tool: Mapped[str] = mapped_column(String(40), index=True)
    arguments: Mapped[dict[str, Any]] = mapped_column(JSONB)
    result: Mapped[dict[str, Any]] = mapped_column(JSONB)  # what the model was shown
    status: Mapped[str] = mapped_column(String(5))
    latency_ms: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    message: Mapped[ChatMessage] = relationship(back_populates="tool_calls")


class KbDocument(Base):
    """An investor-education article of the knowledge base (app/chatbot/knowledge/*.md)."""

    __tablename__ = "kb_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True)  # file name without .md
    title: Mapped[str] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(String(300))
    content_hash: Mapped[str] = mapped_column(String(64))  # re-embed only when the text changes
    embedding_model: Mapped[str] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    chunks: Mapped[list["KbChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="KbChunk.chunk_index"
    )


class KbChunk(Base):
    """A passage of a document with its embedding, searched by cosine similarity."""

    __tablename__ = "kb_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_kb_chunks_document_index"),
        # Approximate nearest-neighbour index (HNSW) for cosine distance, the <=> operator.
        Index(
            "ix_kb_chunks_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("kb_documents.id", ondelete="CASCADE"))
    chunk_index: Mapped[int] = mapped_column(SmallInteger)
    heading: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS))

    document: Mapped[KbDocument] = relationship(back_populates="chunks")
