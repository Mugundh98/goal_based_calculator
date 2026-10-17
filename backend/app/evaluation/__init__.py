"""Evaluation (Phase 12): reports on the ML models, the return models and the assistant.

    uv run python -m app.evaluation ml         # walk-forward results vs naive baselines
    uv run python -m app.evaluation returns    # chance of success under the 4 return models
    uv run python -m app.evaluation chatbot    # ~100-question test set against Gemini

Each writes docs/evaluation/<name>.md (for the report) and <name>.json (the raw numbers).
"""
