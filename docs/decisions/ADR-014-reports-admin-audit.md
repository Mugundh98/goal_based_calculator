# ADR-014: Reports and administration – ReportLab PDF, role-based admin API, append-only audit log

**Status:** Accepted · **Date:** 2026-10-17 · **Phase:** 11

## Context

Phase 11 lets users take their plan away as a document, gives administrators a view of the system (users, data pipeline, model versions, assistant use), and keeps a record of key actions for accountability and security. The role column and `require_admin` guard exist since Phase 1, but nothing used them and there was no way to create an administrator.

## Options considered

| Question | Options | Chosen | Why |
|---|---|---|---|
| PDF engine | WeasyPrint (HTML → PDF); headless browser; **ReportLab** | **ReportLab (platypus)** | Pure Python, no GTK/Pango or browser to install on Windows or the deployment server; tables and simple vector charts are enough |
| Where to render | Browser (print page); **server** | **Server-side, from the same services the pages use** | One consistent document; works without a browser print dialog; testable (text extracted with pypdf) |
| Rupee sign | Embed a TTF font; **"Rs"** | **"Rs 1,25,000" with Indian grouping** | The 14 built-in PDF fonts lack ₹; bundling a font adds size and licensing to every file |
| Who gets admin | Sign-up flag; first user; **command line** | **`python -m app.admin make-admin <email>`** (audited) | No way to become admin through the web; needs server access |
| Admin authorisation | Check in each route; **dependency** | **`AdminUser` = `Depends(require_admin)`** on every admin route; the role is read from the database on every request | A demoted or deactivated admin loses access at once, even with an old token |
| Self-lockout | Allow; **forbid** | **An admin cannot change their own role or deactivate themselves** (409) | The last admin cannot lock everyone out |
| Audit storage | Log file; **table** | **`audit_log` table** (who, what, entity, details JSONB, IP, time) | Queryable from the admin dashboard; survives restarts; backed up with the data |
| Tamper resistance | Trust the code; **trigger** | **A PostgreSQL trigger raises on any UPDATE or DELETE** | Not even a bug or a compromised application account using normal SQL can rewrite history (only a database superuser disabling the trigger could) |
| Actor reference | Foreign key to users; **id + e-mail snapshot** | **No foreign key** | Deleting a user must not delete or change the record of what they did |
| When to record | Database triggers on every table; **after the action, in the route** | **After the service call succeeds (`Audit` dependency), failed logins too** | Records what actually happened, with the user and IP that only the request knows; simple. Trade-off: the action and its audit row are two commits, so a crash between them could lose one row |
| What to record | Every request; **key actions** | **22 actions**: sign-up, login (and failures), profile, risk, goals, retirement, simulations, recommendations, portfolio, assistant-created goals, report downloads, admin changes, job runs, model activation, CLI role changes | Meaningful events, not noise; reads are not logged |
| Model versions | Retrain to roll back; **activate an old version** | **Admin can activate any stored version** (partial unique index keeps one active) | Instant rollback of a bad retraining |

## Decision

`app/models/audit.py` + migration `0012` (table, indexes, trigger); `app/services/audit.py` (`record`, `Auditor`, `entries`, `last_logins`, `ACTIONS`); `Audit` and `AdminUser` dependencies in `app/api/deps.py`; `app/reports/plan_pdf.py` (pure renderer) + `app/services/reports.py` + `GET /api/reports/plan`; `app/services/admin.py` + `/api/admin/*`; `app/admin.py` CLI; frontend "Download my plan" button and `/admin` dashboard behind `AdminRoute`.

## Consequences

- Administrators see users, activity, data freshness, job runs, model versions and assistant quality (fallbacks, unverified numbers, tool errors and latency) in one place.
- Every key change is traceable to a person, time and address, and the trail cannot be edited.
- The PDF is generated in about 0.25 s and is about 8 KB for a typical plan; it shows "Rs" rather than "₹".
- Not covered: exporting the audit log, retention policy (rows are kept forever), e-mailing the PDF, charts beyond bars in the PDF.
