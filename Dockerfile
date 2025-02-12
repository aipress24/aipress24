FROM python:3.12

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
RUN cp /root/.local/bin/uv /usr/local/bin/uv
RUN apt-get update && apt-get install -y postgresql-client vim redis-server

WORKDIR /app

RUN adduser app
RUN chown -R app:app .


COPY pyproject.toml .
COPY uv.lock .
COPY README.md .
COPY wsgi.py .
COPY Procfile .

COPY migrations migrations
COPY icons icons
COPY vite/dist vite/dist
COPY etc etc
COPY scripts scripts
COPY src src
COPY db db
COPY users users
RUN mkdir logs

RUN chown -R app:app .

USER app

RUN uv sync --frozen --no-dev
RUN ln -s .venv/bin bin
RUN DATABASE_URL='sqlite:///' bin/flask check

ENV PORT=8080
ENV PATH=/app/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

CMD ["honcho", "start"]

# CMD ["/app/.venv/bin/python", "-m", "server"]
