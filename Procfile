# Procfile used by PaaS operators like Heroku, Hop3, etc.

release: flask db upgrade
web: python -m server
worker: flask queue worker --threads 4
scheduler: flask queue scheduler

# release: scripts/release.py
# web: scripts/run.py
# web: honcho -f Procfile.heroku start
# web: gunicorn -w4 -b 0.0.0.0:$PORT 'wsgi:create_app()'
