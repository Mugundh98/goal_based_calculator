"""A scripted stand-in for Gemini, so assistant tests need no API key and no network."""

import hashlib
import math
import re
from collections.abc import Iterator, Sequence
from typing import Any, Literal

from app.chatbot.llm import Chunk, HistoryMessage, ToolCallRequest, ToolResult, ToolSpec
from app.models.chat import EMBEDDING_DIMENSIONS

Step = list[Chunk] | Exception


def say(text: str) -> list[Chunk]:
    """An answer streamed in two pieces."""
    half = len(text) // 2
    return [Chunk(text=text[:half]), Chunk(text=text[half:])]


def call(tool: str, **args: Any) -> list[Chunk]:
    return [Chunk(calls=(ToolCallRequest(tool, args, f"call-{tool}"),))]


def fake_embedding(text: str) -> list[float]:
    """Bag of hashed words: texts sharing words point in similar directions."""
    vector = [0.0] * EMBEDDING_DIMENSIONS
    for word in re.findall(r"[a-z]{3,}", text.lower()):
        vector[int(hashlib.md5(word.encode()).hexdigest(), 16) % EMBEDDING_DIMENSIONS] += 1
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


class FakeConversation:
    def __init__(self, llm: "FakeLLM", system: str, history: Sequence[HistoryMessage]):
        self.llm = llm
        self.system = system
        self.history = list(history)
        self.model = llm.chat_model
        self.sent: list[str] = []
        self.results: list[list[ToolResult]] = []

    def send(self, text: str) -> Iterator[Chunk]:
        self.sent.append(text)
        return self._next()

    def send_tool_results(self, results: Sequence[ToolResult]) -> Iterator[Chunk]:
        self.results.append(list(results))
        return self._next()

    def _next(self) -> Iterator[Chunk]:
        step = self.llm.script.pop(0) if self.llm.script else say("(no more script)")
        if isinstance(step, Exception):
            raise step
        yield from step


class FakeLLM:
    chat_model = "fake-chat"
    embedding_model = "fake-embedding"

    def __init__(self, *script: Step) -> None:
        self.script: list[Step] = list(script)
        self.conversations: list[FakeConversation] = []
        self.tools: list[ToolSpec] = []
        self.embedded: list[str] = []

    def conversation(
        self, system: str, history: Sequence[HistoryMessage], tools: Sequence[ToolSpec]
    ) -> FakeConversation:
        self.tools = list(tools)
        conversation = FakeConversation(self, system, history)
        self.conversations.append(conversation)
        return conversation

    def embed(self, texts: Sequence[str], task: Literal["document", "query"]) -> list[list[float]]:
        self.embedded.extend(texts)
        return [fake_embedding(t) for t in texts]
