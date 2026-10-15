# ADR-007: Market data pipeline – free sources, ETL with idempotent upserts, stored fund metrics

**Status:** Accepted · **Date:** 2026-10-15 · **Phase:** 4

## Context

From Phase 4 on, GoalWise needs real market data: the NAV history of Indian mutual funds (for fund metrics now, for ML features in Phase 7 and for recommendations in Phase 8), benchmark index levels, and consumer price inflation. The data must:

1. cost nothing and need no API keys (a student project; nothing to leak or renew),
2. refresh automatically every business day,
3. survive re-runs, partial failures and overlapping loads without duplicates,
4. keep a record of what was loaded and what was rejected (data quality),
5. let the fund explorer sort thousands of funds by return and risk quickly.

## Options considered

| Question | Options | Chosen | Why |
|---|---|---|---|
| Daily NAVs | AMFI `NAVAll.txt`; paid data vendors; scraping fund house sites | **AMFI `NAVAll.txt`** | Official, free, every scheme in one file, published every business evening |
| NAV history | AMFI history report (90-day windows, one request per window); mfapi.in (free mirror of AMFI data, full history per scheme); paid APIs | **mfapi.in, cached on disk** | One request per fund instead of ~40; no key. Cache makes the backfill resumable and avoids downloading again |
| Index levels | NSE website (blocks automated downloads); Yahoo Finance via `yfinance`; paid APIs | **`yfinance`** | Free, long history (Nifty 50 since 2007), maintained library handles Yahoo's request format |
| Inflation | MOSPI CPI API; World Bank (annual only); RBI DBIE (manual downloads) | **MOSPI API** | Official monthly CPI, free, no key. Its server needs legacy TLS renegotiation, enabled for that client only |
| ETL or ELT | Load raw files, transform in SQL (ELT); transform in Python, then load (ETL) | **ETL** | The raw files are not tabular (section lines carry the category and fund house), contain "N.A." and zero NAVs and mixed encodings. Validating before loading keeps bad rows out and counts them |
| Loading | Delete and re-insert; plain INSERT; `INSERT … ON CONFLICT DO UPDATE` | **Upsert on the natural key, update only if a value changed, chunked multi-row statements** | Idempotent (a re-run writes 0 rows), no window where data is missing, no dead rows for unchanged data, one round trip per few thousand rows |
| `nav_history` key | Surrogate `id` + unique (fund_id, nav_date); composite primary key | **Composite PK (fund_id, nav_date)** | The pair *is* the identity; its index serves the only query (one fund, date range); no extra 4 bytes and index per row on the largest table |
| Fund metrics | Compute on every request; store and refresh after each load | **Store (`fund_metrics`), recompute after `daily_nav`** | Each needs the fund's whole history (thousands of rows); the explorer sorts all funds by them; they change only when new NAVs arrive. (Contrast ADR-006: goal projections are cheap and depend on today's date, so they are computed on read) |
| Metric number type | `NUMERIC`; `double precision` | **`double precision`** | Derived statistics, not money; recomputed nightly (stored NAVs stay exact `NUMERIC`) |
| Risk statistics frequency | Daily returns; monthly returns | **Monthly returns over the last 3 years** | Factsheet convention; daily NAVs are noisy and have holiday gaps |
| Scheduler | OS cron/Task Scheduler; Celery + Redis; APScheduler in the API process | **APScheduler**, plus a CLI for manual runs | No extra infrastructure; a timetable defined in code. Enabled in one process only (`SCHEDULER_ENABLED`) |
| Preventing concurrent runs | Nothing; PostgreSQL advisory lock; partial unique index on running rows | **Partial unique index `uq_job_runs_one_running`** | Enforced by the database itself, visible in the job log, works across processes. A 'running' row older than 6 hours is marked abandoned so a crash cannot block a job forever |

## Decision

- `backend/app/data_pipeline/` holds one module per source (`amfi`, `mfapi`, `indices`, `cpi`) with pure parse functions, `loaders.py` with the upserts and `jobs.py` with the jobs and the runner that writes `job_runs`.
- Pure statistics live in `backend/app/finance/fund_metrics.py` and reuse `tvm.cagr` and `tvm.monthly_rate`.
- The universe for the history backfill is **open-ended, direct-plan, growth-option** funds in equity, hybrid, index and debt categories that published a NAV in the last 30 days (1,482 funds on 15 Oct 2026). Other funds still get the daily NAV.
- Default risk-free rate 6% a year (`RISK_FREE_RATE`), stored with each metrics row.

## Consequences

- No accounts or keys anywhere in the pipeline. mfapi.in and Yahoo Finance are unofficial; if either disappears, only the backfill or the index job needs a new source – parsers and loaders are separate.
- The CPI series currently ends in December 2025: MOSPI moved to base year 2024 in January 2026 and the API does not yet serve the new series. The base year is part of the key, so it can be added later.
- Expense ratios are not loaded yet (AMFI publishes them in a separate disclosure); the column exists and is shown as unavailable.
- `nav_history` grows by ~14,000 rows per business day (all schemes), plus the one-time backfill (~2.5 million rows, 167 MB with indexes).
