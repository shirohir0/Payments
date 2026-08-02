# syntax=docker/dockerfile:1

FROM python:3.12-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=true

WORKDIR /app
RUN pip install --no-cache-dir poetry==2.2.1
COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-root --no-ansi

FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app
RUN groupadd --gid 10001 payments \
    && useradd --uid 10001 --gid payments --no-create-home --shell /usr/sbin/nologin payments

COPY --from=builder --chown=payments:payments /app/.venv /app/.venv
COPY --chown=payments:payments app ./app
COPY --chown=payments:payments alembic.ini ./

USER payments:payments
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header"]
