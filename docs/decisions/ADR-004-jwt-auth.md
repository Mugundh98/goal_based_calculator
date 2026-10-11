# ADR-004: Stateless JWT authentication with Argon2id password hashing

**Status:** Accepted · **Date:** 2026-10-11 · **Phase:** 1

## Context

The React app (later on Vercel) and the API (later on Render) run on different domains. Every user-owned resource needs a reliable user identity. The chatbot (Phase 10) will call the same API on the user's behalf.

## Options considered

| Topic | Option | For | Against |
|---|---|---|---|
| Session mechanism | Server sessions + cookie | Easy revocation | Server state; cross-domain cookies and CSRF handling |
| | **JWT bearer token** | Stateless; standard for SPAs and APIs; works across domains | Cannot be revoked before expiry without extra work |
| Password hashing | bcrypt (passlib) | Widely used | passlib unmaintained; not memory-hard |
| | **Argon2id (pwdlib)** | Memory-hard; OWASP first choice | Uses more memory per login (64 MB, brief) |
| Token storage in browser | Memory only | Not readable after reload; safest against XSS | User logged out on every reload |
| | httpOnly cookie | Not readable by scripts | Needs CSRF protection and cross-site cookie setup |
| | **localStorage + short expiry** | Survives reload; simple | Readable by scripts if XSS occurs |

## Decision

HS256-signed JWT access tokens (60 minutes) issued by an OAuth2 password-flow login endpoint; Argon2id password hashes; token kept in `localStorage` with its expiry; user re-loaded from the database on every request.

## Consequences

- Deactivated or deleted users are rejected immediately; a copied token of an active user stays valid until expiry.
- Users log in again after 60 minutes (no refresh token yet).
- Future work: refresh tokens, httpOnly cookie storage, token revocation list, password reset.
