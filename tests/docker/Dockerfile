# Test runner image. Build context is the repo root (see compose.yaml).
FROM python:3.12-slim

# WeasyPrint renders the justificatif PDFs through Pango; the admin
# database export runs pg_dump.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /usr/local/bin/uv

ENV UV_LINK_MODE=copy \
    PATH=/app/.venv/bin:$PATH
WORKDIR /app

# Dependencies first, so editing code doesn't reinstall them.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-install-project

COPY etc/settings.toml etc/settings.toml
COPY bootstrap_data bootstrap_data
COPY icons/svg icons/svg
COPY migrations migrations
COPY static-pages static-pages
COPY vite/dist vite/dist
COPY sdk/python sdk/python
COPY src src
COPY tests tests
RUN uv sync --frozen

CMD ["pytest", "tests"]
