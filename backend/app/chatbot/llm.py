"""The language model behind the assistant, behind a small interface.

The orchestrator only sees `LLM` and `Conversation`: it sends text or tool results and gets a
stream of chunks (text pieces and function calls). `GeminiLLM` implements them with Google's
`google-genai` SDK; the tests use a scripted fake, so they never need a key or the network.
"""

import math
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Literal, Protocol

import httpx
from google import genai
from google.genai import errors, types

from app.core.config import get_settings
from app.models.chat import EMBEDDING_DIMENSIONS

RETRYABLE = {429, 500, 502, 503, 504}
EMBED_BATCH = 50


@dataclass(frozen=True)
class HistoryMessage:
    role: Literal["user", "assistant"]
    text: str


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON schema of the arguments


@dataclass(frozen=True)
class ToolCallRequest:
    name: str
    args: dict[str, Any]
    id: str | None = None  # Gemini's id for the call, echoed in the response


@dataclass(frozen=True)
class ToolResult:
    call: ToolCallRequest
    data: dict[str, Any]  # what the model is shown


@dataclass(frozen=True)
class Chunk:
    text: str = ""
    calls: tuple[ToolCallRequest, ...] = field(default_factory=tuple)


class LLMError(Exception):
    """The model could not answer. `kind` decides the message the user sees."""

    def __init__(self, kind: Literal["rate_limit", "unavailable", "config"], detail: str) -> None:
        super().__init__(detail)
        self.kind = kind


class Conversation(Protocol):
    model: str  # the model that produced the last answer

    def send(self, text: str) -> Iterator[Chunk]: ...

    def send_tool_results(self, results: Sequence[ToolResult]) -> Iterator[Chunk]: ...


class LLM(Protocol):
    chat_model: str
    embedding_model: str

    def conversation(
        self, system: str, history: Sequence[HistoryMessage], tools: Sequence[ToolSpec]
    ) -> Conversation: ...

    def embed(
        self, texts: Sequence[str], task: Literal["document", "query"]
    ) -> list[list[float]]: ...


def normalise(vector: Sequence[float]) -> list[float]:
    """Unit length, so cosine similarity is a dot product (needed for truncated embeddings)."""
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


def _error(exc: Exception) -> LLMError:
    if isinstance(exc, errors.APIError):
        if exc.code == 429:
            return LLMError("rate_limit", str(exc))
        if exc.code in (400, 401, 403) and "key" in str(exc).lower():
            return LLMError("config", str(exc))
        return LLMError("unavailable", str(exc))
    return LLMError("unavailable", str(exc))


class GeminiConversation:
    """One question's exchange with Gemini; keeps the provider's message list between rounds."""

    def __init__(
        self,
        client: genai.Client,
        models: Sequence[str],
        system: str,
        history: Sequence[HistoryMessage],
        tools: Sequence[ToolSpec],
    ) -> None:
        self.client = client
        self.models = list(models)
        self.model = self.models[0]
        self.contents: list[types.Content] = [
            types.Content(
                role="user" if m.role == "user" else "model", parts=[types.Part(text=m.text)]
            )
            for m in history
        ]
        self.config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.2,  # factual answers; the numbers come from tools anyway
            tools=[
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(
                            name=t.name,
                            description=t.description,
                            parameters_json_schema=t.parameters,
                        )
                        for t in tools
                    ]
                )
            ],
        )

    def send(self, text: str) -> Iterator[Chunk]:
        self.contents.append(types.Content(role="user", parts=[types.Part(text=text)]))
        return self._stream()

    def send_tool_results(self, results: Sequence[ToolResult]) -> Iterator[Chunk]:
        parts = [
            types.Part(
                function_response=types.FunctionResponse(
                    id=r.call.id, name=r.call.name, response={"result": r.data}
                )
            )
            for r in results
        ]
        self.contents.append(types.Content(role="user", parts=parts))
        return self._stream()

    def _stream(self) -> Iterator[Chunk]:
        for attempt, model in enumerate(self.models):
            parts: list[types.Part] = []
            emitted = False
            try:
                stream = self.client.models.generate_content_stream(
                    model=model, contents=self.contents, config=self.config
                )
                for response in stream:
                    candidate = response.candidates[0] if response.candidates else None
                    if candidate is None or candidate.content is None:
                        continue
                    for part in candidate.content.parts or []:
                        parts.append(part)  # kept whole: thought signatures must go back
                        if part.thought:
                            continue
                        if part.function_call:
                            emitted = True
                            call = part.function_call
                            yield Chunk(
                                calls=(
                                    ToolCallRequest(
                                        call.name or "", dict(call.args or {}), call.id
                                    ),
                                )
                            )
                        elif part.text:
                            emitted = True
                            yield Chunk(text=part.text)
            except (errors.APIError, httpx.HTTPError) as exc:
                code = exc.code if isinstance(exc, errors.APIError) else 503
                last = attempt == len(self.models) - 1
                if emitted or last or code not in RETRYABLE:
                    raise _error(exc) from exc
                continue  # nothing shown yet: try the fallback model
            self.model = model
            self.contents.append(types.Content(role="model", parts=parts))
            return


class GeminiLLM:
    def __init__(self, api_key: str, chat_model: str, fallback_model: str, embedding_model: str):
        self.client = genai.Client(api_key=api_key)
        self.chat_model = chat_model
        self.fallback_model = fallback_model
        self.embedding_model = embedding_model

    def conversation(
        self, system: str, history: Sequence[HistoryMessage], tools: Sequence[ToolSpec]
    ) -> GeminiConversation:
        models = [self.chat_model]
        if self.fallback_model and self.fallback_model != self.chat_model:
            models.append(self.fallback_model)
        return GeminiConversation(self.client, models, system, history, tools)

    def embed(self, texts: Sequence[str], task: Literal["document", "query"]) -> list[list[float]]:
        task_type = "RETRIEVAL_DOCUMENT" if task == "document" else "RETRIEVAL_QUERY"
        vectors: list[list[float]] = []
        try:
            for start in range(0, len(texts), EMBED_BATCH):
                response = self.client.models.embed_content(
                    model=self.embedding_model,
                    contents=list(texts[start : start + EMBED_BATCH]),
                    config=types.EmbedContentConfig(
                        task_type=task_type, output_dimensionality=EMBEDDING_DIMENSIONS
                    ),
                )
                vectors.extend(normalise(e.values or []) for e in response.embeddings or [])
        except (errors.APIError, httpx.HTTPError) as exc:
            raise _error(exc) from exc
        return vectors


@lru_cache
def default_llm() -> GeminiLLM | None:
    """The configured Gemini client, or None when no API key is set (assistant off)."""
    settings = get_settings()
    if not settings.gemini_api_key:
        return None
    return GeminiLLM(
        settings.gemini_api_key,
        settings.gemini_model,
        settings.gemini_fallback_model,
        settings.gemini_embedding_model,
    )
