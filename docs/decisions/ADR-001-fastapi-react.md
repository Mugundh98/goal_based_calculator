# ADR-001: FastAPI backend with a React frontend

**Status:** Accepted · **Date:** 2026-10-10 · **Phase:** 0

## Context

The project needs a web UI, a database and heavy Python computation (simulation, ML), plus an LLM chatbot that calls application functions. The project guide confirmed Python is allowed.

## Options considered

| Option | For | Against |
|---|---|---|
| Django (server-rendered templates) | Built-in admin, auth, ORM | Less interactive UI; frontend and backend tightly coupled |
| Flask + Jinja | Simple | Manual validation, no automatic API docs |
| Streamlit | Very fast to prototype | Limited UI control; not a real multi-user web app |
| **FastAPI + React** | Clear API/UI split; automatic OpenAPI docs; Pydantic validation; async; modern interactive UI | Auth, admin screens and forms must be built by hand |

## Decision

FastAPI for a JSON REST API; React + TypeScript (Vite) for a single-page frontend.

## Consequences

- The same API serves the UI and the chatbot's function calls.
- More work for authentication and admin pages (Phases 1 and 11).
- Two codebases with their own tooling, both checked in CI.
