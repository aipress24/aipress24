# Procfile used by PaaS operators like Heroku, Hop3, etc.

release: scripts/release.py
web: python -m server

# web: scripts/run.py
# web: honcho -f Procfile.heroku start
# web: gunicorn -w4 -b 0.0.0.0:$PORT 'wsgi:create_app()'
# scheduler: flask rq scheduler
# worker: flask rq worker
