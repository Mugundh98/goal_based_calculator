# ADR-003: uv for Python dependency and version management

**Status:** Accepted · **Date:** 2026-10-10 · **Phase:** 0

## Context

The backend needs a reproducible Python environment. The development machine has Python 3.13, but ML libraries planned for later phases (`arch`, `hmmlearn`) have the most reliable pre-built packages for Python 3.12.

## Options considered

| Option | For | Against |
|---|---|---|
| pip + venv + requirements.txt | Built in | No lockfile for indirect dependencies; Python version installed separately |
| Poetry | Lockfile, popular | Slower; does not install Python itself |
| **uv** | Very fast; lockfile (`uv.lock`); installs the required Python version | Newer tool |

## Decision

uv, with Python pinned to 3.12 in `pyproject.toml` and `.python-version`.

## Consequences

- `uv sync` reproduces the exact environment locally and in CI.
- Commands are run as `uv run <command>`.
