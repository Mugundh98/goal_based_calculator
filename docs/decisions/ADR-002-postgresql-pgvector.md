# ADR-002: PostgreSQL with pgvector as the only database

**Status:** Accepted · **Date:** 2026-10-10 · **Phase:** 0

## Context

The system stores relational data (users, goals, transactions), large time series (daily NAVs) and, from Phase 10, text embeddings for the chatbot. The database must be free.

## Options considered

| Option | For | Against |
|---|---|---|
| SQLite | Zero setup | Weak concurrency; no vector search; differs from production |
| MySQL | Free, popular | Weaker JSON and extension support |
| Oracle XE | Named in the university guidelines | Heavy, resource-limited; the guide confirmed any free database is fine |
| PostgreSQL + a separate vector database | Specialised vector search | Two systems to run and keep consistent |
| **PostgreSQL + pgvector** | Free; strong SQL, JSONB and indexing; vectors in the same database | Extension must be installed (solved by the Docker image) |

## Decision

PostgreSQL 16 with pgvector, run locally via Docker (`pgvector/pgvector:pg16`), schema managed by Alembic.

## Consequences

- One database for all data; embeddings can be joined with relational data.
- Docker Desktop is required for local development.
