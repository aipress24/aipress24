# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Shared helpers for Marketplace offer views (missions, projects, jobs).

All offer types share the same lifecycle (`OPEN → FILLED/CLOSED`), the
same candidature flow (`OfferApplication`), the same e-mail
notification to the emitter, and the same owner-only authorization
checks. Per-type view modules delegate here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from flask import abort, flash, g, redirect, request, url_for

from app.flask.extensions import db
from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.modules.biz.models import (
    ApplicationStatus,
    MissionStatus,
    OfferApplication,
)
from app.modules.biz.services.offer_notifications import (
    notify_applicant_rejected,
    notify_applicant_selected,
    notify_emitter_of_application,
)


def get_offer_or_404(model: type, id: int):
    """Load an offer of the given type, enforce visibility rules.

    Visible to anyone when `status == PUBLIC`. Also visible to the
    owner and admins when `status == PENDING` (moderation in progress)
    so the submitter can still see and edit their offer.
    """
    offer = db.session.get(model, id)
    if offer is None:
        abort(404)
    if offer.status == PublicationStatus.PUBLIC:
        return offer
    if offer.status == PublicationStatus.PENDING:
        user = cast(User, g.user)
        if not user.is_anonymous and user.id == offer.owner_id:
            return offer
    abort(404)
    return None  # unreachable, keeps the type-checker happy


def default_new_offer_status():
    """Return PublicationStatus to assign to a freshly-created offer.

    When `MARKETPLACE_MODERATION_REQUIRED` is truthy, new offers go
    to `PENDING` (hidden from listings, awaiting admin review).
    """
    from flask import current_app

    if current_app.config.get("MARKETPLACE_MODERATION_REQUIRED"):
        return PublicationStatus.PENDING
    return PublicationStatus.PUBLIC


def get_user_application(offer_id: int, user: User) -> OfferApplication | None:
    if user.is_anonymous:
        return None
    return (
        db.session.query(OfferApplication)
        .filter_by(offer_id=offer_id, owner_id=user.id)
        .first()
    )


def handle_apply(
    offer, *, detail_endpoint: str, cv_url: str = ""
):
    """Submit a candidature on an offer. Returns a Flask response."""
    user = cast(User, g.user)

    if user.is_anonymous:
        flash("Connexion requise pour candidater.", "error")
        return redirect(url_for("security.login"))

    if user.id == offer.owner_id:
        flash(
            "Vous ne pouvez pas candidater à votre propre offre.", "error"
        )
        return redirect(url_for(detail_endpoint, id=offer.id))

    if offer.mission_status != MissionStatus.OPEN:
        flash("Cette offre n'accepte plus de candidatures.", "error")
        return redirect(url_for(detail_endpoint, id=offer.id))

    existing = get_user_application(offer.id, user)
    if existing is not None:
        flash("Vous avez déjà candidaté à cette offre.", "info")
        return redirect(url_for(detail_endpoint, id=offer.id))

    message = (request.form.get("message") or "").strip()
    application = OfferApplication(
        offer_id=offer.id,
        owner_id=user.id,
        message=message,
        cv_url=cv_url,
    )
    db.session.add(application)
    db.session.commit()

    notify_emitter_of_application(mission=offer, application=application)

    flash("Candidature envoyée.", "success")
    return redirect(url_for(detail_endpoint, id=offer.id))


def list_applications(offer):
    return (
        db.session.query(OfferApplication)
        .filter_by(offer_id=offer.id)
        .order_by(OfferApplication.created_at.desc())
        .all()
    )


def require_owner(offer) -> User:
    user = cast(User, g.user)
    if user.is_anonymous or user.id != offer.owner_id:
        abort(403)
    return user


def update_application_status(
    offer, app_id: int, new_status: ApplicationStatus, redirect_endpoint: str
):
    require_owner(offer)
    application = db.session.get(OfferApplication, app_id)
    if application is None or application.offer_id != offer.id:
        abort(404)

    previous_status = application.status
    application.status = new_status
    db.session.commit()

    if previous_status != new_status:
        if new_status == ApplicationStatus.SELECTED:
            notify_applicant_selected(offer=offer, application=application)
        elif new_status == ApplicationStatus.REJECTED:
            notify_applicant_rejected(offer=offer, application=application)

    flash(f"Candidature {new_status.value}.", "success")
    return redirect(url_for(redirect_endpoint, id=offer.id))


def mark_filled(offer, redirect_endpoint: str):
    require_owner(offer)
    offer.mission_status = MissionStatus.FILLED
    db.session.commit()
    flash("Offre marquée comme pourvue.", "success")
    return redirect(url_for(redirect_endpoint, id=offer.id))


def euros_to_cents(value: int | None) -> int | None:
    return None if value is None else value * 100


def date_to_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    return datetime.combine(value, datetime.min.time())
