#!/bin/sh
# AIPress24 — configuration for a BLANK / CI deploy on Hop3.
# Safe to commit and run: it sets NO secrets.
#
# The app runs in the default (development) Dynaconf environment, whose committed
# defaults already satisfy everything required at boot — S3 settings (MinIO-style
# dummies), a file-based mail backend, and a dev SECRET_KEY — so the app comes up
# with no real integrations. Then:
#   - FLASK_SEED_BLANK=true  makes before-run seed an empty DB (reference data +
#                            the demo users in users/*.yaml) so the app is usable.
#   - FLASK_SERVER_NAME=''   lifts Flask's host check so the app answers on
#                            whatever hostname CI deploys it to.
#
# Usage:
#     sh scripts/hop3-ci-config.sh [app-name]
#     hop3 deploy aipress24
set -eu
APP="${1:-aipress24}"

hop3 config set "$APP" \
    FLASK_SEED_BLANK=true \
    FLASK_SERVER_NAME=

echo "CI config applied to '$APP'. Now: hop3 deploy $APP"
