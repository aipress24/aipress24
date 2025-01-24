FROM python:3.12

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
RUN cp /root/.local/bin/uv /usr/local/bin/uv

WORKDIR /app

RUN adduser app
RUN chown -R app:app .

USER app

# Used only for bootstrapping
COPY data data

COPY pyproject.toml .
COPY uv.lock .
COPY README.md .
COPY wsgi.py .

COPY src src
COPY migrations migrations
COPY icons icons
COPY vite/dist vite/dist
COPY etc etc

RUN uv sync --frozen

#CMD [".venv/bin/flask", "run", "--port=8080"]
#CMD ["/app/.venv/bin/gunicorn", "-w", "4", "-b", "0.0.0.0:8080", "wsgi:app"]

ENV PORT=8080
CMD ["/app/.venv/bin/python", "-m", "server"]
