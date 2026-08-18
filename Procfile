# Procfile used by PaaS operators like Heroku, Hop3, etc.
#
# `release` is a release-phase hook, not a process. honcho has no notion of
# release phases: it starts the line like any other process, and it kills
# every process as soon as one of them exits — so `honcho -f Procfile start`
# tears the whole stack down the moment the migration succeeds. Locally, use
# `make run` (Procfile-dev) or `make run-prod` (this file, release excluded).

release: flask db upgrade
web: python -m server
worker: flask queue worker --threads 4
scheduler: flask queue scheduler

# release: scripts/release.py
# web: scripts/run.py
# web: honcho -f Procfile.heroku start
# web: gunicorn -w4 -b 0.0.0.0:$PORT 'wsgi:create_app()'
