# GoalWise API image (Phase 13). Built by Render from backend/ (see render.yaml); also runs locally:
#   docker build -t goalwise-api backend
#   docker run --rm -p 8000:8000 -e DATABASE_URL=... -e JWT_SECRET_KEY=... goalwise-api
FROM python:3.12-slim

# LightGBM needs the OpenMP runtime, which the slim image leaves out.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# The same uv that wrote uv.lock, so the lockfile is read exactly as in development and CI.
COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /usr/local/bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Dependencies first: this layer is reused until pyproject.toml or uv.lock changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

# Run as an unprivileged user; data/ is the only place the app writes (pipeline cache, models).
RUN useradd --create-home --uid 10001 goalwise && mkdir -p data && chown goalwise data
USER goalwise

# Render sets PORT; 8000 elsewhere. Migrations run on every start (a no-op when up to date),
# then one uvicorn worker: the free plan has 512 MB of memory.
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips='*'"]
