# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin — Marketplace offers moderation queue.

Visible when `MARKETPLACE_MODERATION_REQUIRED` is set. Otherwise the
queue stays empty and the page is a harmless placeholder.
"""

from __future__ import annotations

import sqlalchemy as sa
from flask import abort, flash, redirect, render_template, url_for

from app.flask.extensions import db
from app.models.lifecycle import PublicationStatus
from app.modules.admin import blueprint
from app.modules.biz.models import MarketplaceContent

_SUPPORTED_KINDS = {"mission_offer", "project_offer", "job_offer"}


@blueprint.route("/biz/moderation")
def biz_moderation():
    """List every PENDING offer awaiting moderation, all kinds."""
    stmt = (
        sa.select(MarketplaceContent)
        .where(MarketplaceContent.status == PublicationStatus.PENDING)
        .where(MarketplaceContent.type.in_(_SUPPORTED_KINDS))
        .order_by(MarketplaceContent.created_at.desc())
    )
    offers = list(db.session.scalars(stmt))
    return render_template(
        "admin/pages/biz_moderation.j2",
        offers=offers,
        title="Modération des offres",
    )


@blueprint.route("/biz/moderation/<int:id>/approve", methods=["POST"])
def biz_moderation_approve(id: int):
    offer = _load_pending_or_404(id)
    offer.status = PublicationStatus.PUBLIC
    db.session.commit()
    flash(f"Offre « {_title(offer)} » publiée.", "success")
    return redirect(url_for(".biz_moderation"))


@blueprint.route("/biz/moderation/<int:id>/reject", methods=["POST"])
def biz_moderation_reject(id: int):
    offer = _load_pending_or_404(id)
    offer.status = PublicationStatus.REJECTED
    db.session.commit()
    flash(f"Offre « {_title(offer)} » rejetée.", "success")
    return redirect(url_for(".biz_moderation"))


def _load_pending_or_404(id: int) -> MarketplaceContent:
    offer = db.session.get(MarketplaceContent, id)
    if (
        offer is None
        or offer.status != PublicationStatus.PENDING
        or offer.type not in _SUPPORTED_KINDS
    ):
        abort(404)
    return offer


def _title(offer: MarketplaceContent) -> str:
    return getattr(offer, "title", f"#{offer.id}")
