#!/bin/sh
# Run by hop3.toml [run].before-run, from the repo root, before the web and
# worker processes start. DATABASE_URL is injected by the postgres addon.
#
# Always brings the schema to head (create_all + stamp on an empty DB, db upgrade
# on a restored/managed one — see scripts/hop3_db_bootstrap.py for why a plain
# `flask db upgrade` can't build this app's schema from empty). Seeds reference
# data + demo users ONLY when FLASK_SEED_BLANK is set, so a real-data deploy
# (flag unset) never touches a populated database while a blank/CI deploy comes
# up usable.
set -eu

echo "[hop3-before-run] database bootstrap"
python scripts/hop3_db_bootstrap.py

case "${FLASK_SEED_BLANK:-}" in
    1 | true | True | TRUE | yes | on)
        echo "[hop3-before-run] FLASK_SEED_BLANK set -> seeding blank database"
        # Idempotent: bootstrap checks existence before inserting; bootstrap-users
        # merges by id. Safe to re-run on every blank/CI deploy.
        flask bootstrap
        flask data bootstrap-users
        echo "[hop3-before-run] seed complete"
        ;;
    *)
        echo "[hop3-before-run] FLASK_SEED_BLANK unset -> migrations only (real-data deploy)"
        ;;
esac
