# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""Script to remove all article purchase rights.

Removes every `ArticlePurchase` record (consultation, justificatif,
cession/reproduction rights) and their associated `ArticlePurchaseGift`
beneficiaries.

Usage: uv run --env-file .env scripts/remove_all_article_purchases.py
"""

from __future__ import annotations

from app.flask.extensions import db
from app.flask.main import create_app
from app.modules.wire.models import ArticlePurchase, ArticlePurchaseGift


def remove_all_article_purchases():
    db_session = db.session

    print("Researching article purchases to remove...")
    purchase_count = db_session.query(ArticlePurchase).count()
    gift_count = db_session.query(ArticlePurchaseGift).count()

    if purchase_count == 0 and gift_count == 0:
        print("No article purchase records found. Nothing to do.")
        return

    print(f"Found {purchase_count} ArticlePurchase records.")
    print(f"Found {gift_count} ArticlePurchaseGift records.")

    if gift_count:
        print("Deleting ArticlePurchaseGift records...")
        db_session.query(ArticlePurchaseGift).delete()

    if purchase_count:
        print("Deleting ArticlePurchase records...")
        db_session.query(ArticlePurchase).delete()

    print("Committing changes...")
    db_session.commit()
    print("Cleanup complete.")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        remove_all_article_purchases()
