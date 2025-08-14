FROM python:3.12-slim-bookworm

RUN apt update && apt upgrade -y && apt install -y zip curl && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy local context to `/app` inside container (see .dockerignore)
WORKDIR /app

COPY pyproject.toml uv.lock .

RUN uv venv

RUN uv sync --locked

COPY . .

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/ping || exit 1

CMD exec uv run reflex run --env prod
