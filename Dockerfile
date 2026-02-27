FROM python:3.12

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
RUN cp /root/.local/bin/uv /usr/local/bin/uv
RUN apt-get update && apt-get install -y postgresql-client vim

WORKDIR /app

RUN adduser app
RUN chown -R app:app .

COPY pyproject.toml .
COPY uv.lock .
COPY README.md .
COPY wsgi.py .

COPY migrations migrations
COPY icons icons
COPY vite/dist vite/dist
COPY etc etc
COPY scripts scripts
COPY src src
# COPY db db
# COPY users users

RUN chown -R app:app .

USER app

RUN uv venv -p python3.12
RUN uv sync -q --frozen --no-dev
RUN ln -s .venv/bin bin
# Smoke test - verify app loads correctly (dummy URL, no actual connection)
RUN DATABASE_URL='postgresql://x:x@localhost/x' bin/flask dev check

ENV PORT=8080
CMD ["/app/.venv/bin/python", "-m", "server"]
