# Procfile used by PaaS operators like Heroku, Hop3, etc.

release: flask db upgrade
web: scripts/run.py

# web: honcho -f Procfile.heroku start
# web: gunicorn -w4 -b 0.0.0.0:$PORT 'wsgi:create_app()'
# scheduler: flask rq scheduler
# worker: flask rq worker
