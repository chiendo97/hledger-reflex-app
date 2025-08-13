FROM python:3.12-slim-bookworm

RUN apt update && apt upgrade -y && apt install -y zip curl

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy local context to `/app` inside container (see .dockerignore)
WORKDIR /app

COPY pyproject.toml uv.lock .

RUN uv venv

RUN uv sync --locked

COPY . .

# Download all npm dependencies and compile frontend
RUN uv run reflex export --frontend-only --no-zip

# Needed until Reflex properly passes SIGTERM on backend.
STOPSIGNAL SIGKILL

CMD ["uv", "run", "reflex", "run", "--env", "prod"]
