# Changelog

All notable changes, one entry per phase tag. Format: [Keep a Changelog](https://keepachangelog.com).

## [0.1.0] – 2026-10-11 – Phase 1: Authentication

### Added

- `users` table (migration `0002`) with unique lower-case email, role check constraint and `is_active` flag.
- `POST /api/auth/register`, `POST /api/auth/login` (OAuth2 password flow, JWT), `GET /api/auth/me`.
- Argon2id password hashing (pwdlib), HS256 JWT tokens (PyJWT) with 60-minute expiry.
- `get_current_user` and `require_admin` dependencies for protecting endpoints.
- Frontend: login and registration pages (react-hook-form + zod), AuthProvider with session restore and auto-logout, axios auth interceptors, protected and guest routes, dashboard; status page moved to `/status`.
- Test suite runs against a dedicated `goalwise_test` database built from migrations, with per-test rollback (28 tests).
- Documentation: Phase 1 document, ADR-004, updated architecture, database and API docs.

## [0.0.1] – 2026-10-10 – Phase 0: Setup and foundations

### Added

- FastAPI backend skeleton with settings, database session and `GET /api/health`.
- PostgreSQL 16 + pgvector via Docker Compose; Alembic with migration `0001` enabling `vector`.
- React 19 + TypeScript + Vite frontend with Tailwind CSS, React Router, TanStack Query and a system status page.
- Vite dev proxy and backend CORS configuration.
- GitHub Actions CI: backend lint, migrations and tests against a real database; frontend lint and build.
- Documentation: project plan, phase template, Phase 0 document, architecture, database, API, ADR-001 to ADR-003.
