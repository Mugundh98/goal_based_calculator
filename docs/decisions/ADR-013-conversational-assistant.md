# ADR-013: Conversational assistant – Gemini function calling over the services, RAG on pgvector, guardrails in code

**Status:** Accepted · **Date:** 2026-10-17 · **Phase:** 10

## Context

Phase 10 adds a chat assistant that answers questions about the user's own plan and explains concepts. A language model writes fluent text but cannot be trusted with arithmetic, with facts it half-remembers, or with the user's data. The assistant must therefore get every number from the app's tested services, every explanation from vetted text, act only for the logged-in user, and fail gracefully.

## Options considered

| Question | Options | Chosen | Why |
|---|---|---|---|
| Model provider | OpenAI; local model; **Gemini** | **Google Gemini** (`google-genai`), `gemini-3.5-flash` with `gemini-2.5-flash` as fallback | Free tier enough for a project; function calling and embeddings in one SDK; the fallback absorbs rate limits (seen in testing) |
| Getting numbers | Model computes; **function calling** | **10 tools that call the existing services** (goals, calculator, create goal, simulation, recommendation, fund search, fund comparison, portfolio, risk profile, knowledge base) | The services are the tested source of truth (Phases 3–9); the model only chooses a tool and words the result |
| Tool schemas | Hand-written JSON; **from Pydantic models** | **Pydantic argument models**, simplified to plain JSON Schema for the declarations | One definition both declares and validates the arguments; invalid arguments go back to the model as an error |
| Explanations | Model's memory; fine-tuning; **RAG** | **20 articles written for the project, chunked by section, embedded (gemini-embedding-001, 768 dims) and stored in pgvector; cosine search with an HNSW index; passages below similarity 0.60 dropped** | Vetted, updatable text without retraining; measured on-topic similarity 0.69–0.77, off-topic ≤ 0.53 |
| Writes | Model saves directly; **preview then confirm** | **`create_goal` saves only when the previous answer showed a preview and asked (`awaiting_confirmation`, enforced in code)** | Human in the loop that a prompt injection cannot bypass by setting `confirmed=true` |
| Hallucinated numbers | Trust the prompt; **check after** | **Grounding check: every number in the answer must match a tool result, the question or the conversation (1% / 0.5 points tolerance, Indian units), else stored and shown as a warning** | Measurable; feeds the Phase 12 evaluation |
| Privacy | Send the profile; **minimum needed** | **No name, e-mail or date of birth in prompts or tool results (age instead)**; tests check it | Personal identifiers are not needed for planning |
| Scope and injection | None; **system prompt + data framing** | **System prompt limits scope and says tool output is data, not instructions; length limit 2,000 characters; 30 questions an hour per user** | Defence in depth; the code-level guards do not depend on the model obeying |
| Delivery | Wait for the full answer; **stream** | **Server-sent events** (`text`, `tool`, `chart`, `error`, `done`); the stream uses its own database session | The user sees tool activity and text as it arrives; SSE is plain HTTP, simpler than WebSockets for one-way streaming |
| Charts | Model describes them; **structured payload** | **Tools return a chart payload kept out of the model's context and drawn with the app's own components** | Fewer tokens; charts identical to the rest of the app |
| Testability | Call Gemini in tests; **interface + fake** | **`LLM` / `Conversation` protocol; a scripted fake in tests; the Gemini adapter tested with a stub client** | CI needs no key or network; every guardrail is tested deterministically |
| Failure | Error page; **fallback** | **Retry once with the fallback model on 429/5xx before anything was shown; otherwise a stored fallback message by error kind** | The rest of the app keeps working |

## Decision

`backend/app/chatbot/` (`llm.py`, `tools.py`, `rag.py`, `orchestrator.py`, `grounding.py`, `prompts.py`, `knowledge/*.md`, CLI `python -m app.chatbot ingest|search`); tables `chat_sessions`, `chat_messages`, `tool_calls`, `kb_documents`, `kb_chunks` (migration `0011`); endpoints under `/api/chat`; frontend `/assistant`. The Phase 5 simulation gained an optional `current_savings` override so the assistant simulates from a goal's recorded investments.

## Consequences

- Every answer is traceable: the tool calls (arguments, result, latency) are stored with it.
- Answers take 3–12 seconds (one model call per round plus the tools); the free tier's rate limits make the fallback model visible in practice.
- The knowledge base must be maintained by hand; tax rules in it carry a "check current rules" caveat.
- Not covered: voice, multiple languages, editing or deleting goals by chat, long-term memory beyond the last 12 messages of a conversation.
