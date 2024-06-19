#!/bin/bash

# - runs Alembic migrations
# - starts Starlite application

set -o errexit
set -o pipefail
set -o nounset

cd /nua/build/src

echo "========================================"
echo "Debugging information"
echo "========================================"
echo Config...
/nua/venv/bin/flask --app 'app.flask.main:create_app()' config

echo "========================================"
/nua/venv/bin/flask --app 'app.flask.main:create_app()' routes
echo "========================================"

echo Running migrations...
/nua/venv/bin/flask --app 'app.flask.main:create_app()' load-db

echo Running migrations...
/nua/venv/bin/flask --app 'app.flask.main:create_app()' db upgrade

#echo Building assets...
#/nua/venv/bin/flask --app 'app.flask.main:create_app()' vite build

echo Starting Flask App...
/nua/venv/bin/gunicorn -b 0.0.0.0:$PORT 'app.flask.main:create_app()'
