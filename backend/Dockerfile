# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# The pip shipped in the base image lags behind its own security fixes.
RUN pip install --no-cache-dir --upgrade "pip>=26.2"

# Dependencies are installed from pyproject.toml alone so this layer is cached
# until the dependency list itself changes.
COPY pyproject.toml README.md ./
RUN mkdir -p app && touch app/__init__.py \
    && pip install --no-cache-dir ".[dev]"

COPY . .
RUN pip install --no-cache-dir --no-deps -e .

# Run as a non-root user. UID/GID are build args so that in development the
# container user can match the host user who owns the bind-mounted source,
# which keeps files written inside the container (caches, generated code)
# owned correctly on the host.
ARG UID=10001
ARG GID=10001
RUN groupadd --gid "$GID" appuser \
    && useradd --create-home --uid "$UID" --gid "$GID" appuser \
    && chown -R "$UID:$GID" /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
