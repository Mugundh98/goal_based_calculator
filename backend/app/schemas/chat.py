from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, StringConstraints

MAX_MESSAGE_CHARS = 2000


class ChatStatus(BaseModel):
    enabled: bool  # False when no Gemini API key is configured
    model: str | None
    knowledge_documents: int
    knowledge_chunks: int


class MessageIn(BaseModel):
    text: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_MESSAGE_CHARS)
    ]


class ToolCallOut(BaseModel):
    tool: str
    arguments: dict[str, Any]
    status: str
    latency_ms: int


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime
    charts: list[dict[str, Any]]
    tools: list[ToolCallOut]
    ungrounded: list[str]  # numbers not found in any tool result or the conversation
    error: str | None  # rate_limit / unavailable / config when the answer is a fallback


class SessionSummary(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime


class SessionDetail(SessionSummary):
    messages: list[MessageOut]
