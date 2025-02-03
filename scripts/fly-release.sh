#!/bin/sh

# This script is run on fly release (ie. after a deploy)
echo "Running fly release script (e.g. alembic migration)"

# We need to wait for the database to be ready before running migrations
sleep 10

# Debug
bin/flask config

# Run migrations
bin/flask db upgrade
