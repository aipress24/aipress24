#!/bin/sh
# AIPress24 — production configuration & secrets for Hop3.
#
# THIS REPO IS PUBLIC — do not commit real secrets. Copy this file, fill in the
# CHANGE_ME values, and run the copy (which is gitignored):
#
#     cp scripts/hop3-config.example.sh scripts/hop3-config.local.sh
#     $EDITOR scripts/hop3-config.local.sh
#     sh scripts/hop3-config.local.sh
#     hop3 app restart aipress24
#
# Re-run after rotating any secret. The real values currently live in the old
# piku scripts (setup.sh / setup_s3.sh / update-stripe-keys.sh) — copying them
# here is the moment to ROTATE them, since they were committed in plaintext.
#
# DATABASE_URL is NOT set here — the postgres addon injects it.
set -eu
APP=aipress24

# --- Non-secret production config (safe, deploy it as-is) ---------------------
# Runs the app in the production Dynaconf environment (HTTPS URLs, no dev
# backdoors). FLASK_* values override etc/settings.toml at runtime.
hop3 config set "$APP" \
    ENV_FOR_DYNACONF=production \
    FLASK_UNSECURE=false \
    FLASK_SERVER_NAME=aipress24.com \
    FLASK_PREFERRED_URL_SCHEME=https \
    FLASK_MAIL_BACKEND=smtp \
    FLASK_MAIL_PORT=587 \
    FLASK_MAIL_USE_TLS=True \
    FLASK_MAIL_DEFAULT_SENDER=contact@aipress24.com \
    FLASK_S3_USE_SSL=true

# --- Infra endpoints (not keys, but fill in with your real hosts) -------------
hop3 config set "$APP" \
    FLASK_MAIL_SERVER="CHANGE_ME.smtp.example.com" \
    FLASK_S3_ENDPOINT_URL="https://CHANGE_ME.your-objectstorage.com" \
    FLASK_S3_BUCKET_NAME="CHANGE_ME-blobs" \
    FLASK_S3_REGION_NAME="" \
    FLASK_TYPESENSE_HOST="CHANGE_ME.example.com"

# --- Secrets (CHANGE_ME — required for a real deploy) -------------------------
# NOTE: FLASK_SECRET_KEY and FLASK_SECURITY_PASSWORD_SALT are NOT set here —
# Hop3 generates them on first deploy (see [env] in hop3.toml). Don't set them
# manually unless you need a specific value.
hop3 config set "$APP" \
    FLASK_MAIL_USERNAME="CHANGE_ME" \
    FLASK_MAIL_PASSWORD="CHANGE_ME" \
    FLASK_S3_ACCESS_KEY_ID="CHANGE_ME" \
    FLASK_S3_SECRET_ACCESS_KEY="CHANGE_ME" \
    FLASK_TYPESENSE_API_KEY="CHANGE_ME" \
    FLASK_SENTRY_DSN="CHANGE_ME"

# --- Stripe (optional — the app boots and runs without it) --------------------
# Price-table / price IDs (prctbl_* / price_*) are not secret; the keys are.
hop3 config set "$APP" \
    FLASK_STRIPE_PUBLIC_KEY="CHANGE_ME" \
    FLASK_STRIPE_SECRET_KEY="CHANGE_ME" \
    FLASK_STRIPE_WEBHOOK_SECRET="CHANGE_ME" \
    FLASK_STRIPE_PRICING_SUBS_MEDIA="prctbl_CHANGE_ME" \
    FLASK_STRIPE_PRICING_SUBS_COM="prctbl_CHANGE_ME" \
    FLASK_STRIPE_PRICING_SUBS_ORGANISATION="prctbl_CHANGE_ME"

echo "Config applied to '$APP'. Now: hop3 app restart $APP"
