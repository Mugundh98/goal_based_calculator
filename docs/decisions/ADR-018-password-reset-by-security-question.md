# ADR-018: "Forgot password" by security question, and the account page

**Status:** Accepted · **Date:** 2026-10-21 · **Version:** 1.2.0 · **Amends:** ADR-004

## Context

Users asked for "Forgot password" on the login page, and for an account page (opened by clicking their name) to see their e-mail and change their password. The usual reset is a link by e-mail, but GoalWise sends no e-mail. A provider would need an account, a sender address and a secret on the server. The project owner chose a security question instead.

## Options considered

| Question | Options | Chosen | Why |
|---|---|---|---|
| How to prove identity without the password | E-mail link (needs a mail provider); admin resets it; **security question** | **A question from a fixed list, answered at sign-up or on the account page** | Works without external services (the owner's choice). The weakness is that answers can be guessed or found out, so the mitigations below matter. |
| Storing the answer | Plain text; **hash** | **Argon2id hash of the answer lower-cased with spaces collapsed**, the same hashing as passwords | A leaked database does not reveal answers. Normalising means "Delhi  public school" matches. |
| Guessing answers | No limit; **lockout** | **5 wrong answers for an address within an hour lock its resets for the rest of the hour (`429`)**, counted from the audit log | Turns guessing into a slow job. No new table: every failure is already recorded as `auth.password_reset_failed`. |
| Revealing accounts | Say "no such account"; **stand-in question** | **An unknown address (or one without a question) gets a stand-in question, the same every time (derived from the address)**; the answer is always hashed and checked, so the reply takes the same time | The first step cannot tell an attacker which e-mails have accounts. |
| Free-text or listed questions | Free text; **list** | **6 listed questions** | Users cannot pick something trivially guessable like "1+1?", and the questions can be shown in a select. |
| Existing accounts | Force a question; **optional, set later** | **Optional in the API; required by the sign-up form; existing users set it on the account page** | Old accounts (and API clients) keep working. Without a question, the reset message says to ask the administrator. |
| Changing the e-mail | Editable; **shown only** | **Shown only** (the owner's choice) | It is the login name. Without verification, a typo would lock the user out. |
| Changing the password or question | Token is enough; **current password again** | **Current password required** | A borrowed, still-logged-in browser cannot take over the account. |

## Consequences

- Migration `0014`. Endpoints `PATCH /api/auth/me`, `PUT /api/auth/password`, `GET /api/auth/security-questions`, `PUT /api/auth/security-question`, and `POST /api/auth/forgot-password/question` and `/reset`. Five new audited actions.
- Tokens issued before a password change stay valid until they expire (60 minutes). A token version on the user would end them at once; that is listed as future work.
- If the e-mail service is added later, the reset can switch to e-mailed links without changing the account page.
