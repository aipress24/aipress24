FROM python:3.12

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
RUN cp /root/.local/bin/uv /usr/local/bin/uv

WORKDIR /app

RUN adduser app
RUN chown -R app:app .

USER app

COPY pyproject.toml .
COPY uv.lock .
COPY README.md .
COPY src src
COPY wsgi.py .

RUN uv sync

CMD [".venv/bin/flask", "run"]
