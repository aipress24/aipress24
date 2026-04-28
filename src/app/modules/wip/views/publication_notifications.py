# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""WIP — Notification de publication (mode B + listings + recipient).

Mode A (from an avis d'enquête) lives on the `AvisEnqueteWipView` CBV.

Spec : `local-notes/specs/notification-publication.md`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import and_, select
from sqlalchemy.orm import selectinload
from svcs.flask import container
from werkzeug import Response

from app.flask.extensions import db
from app.models.auth import User
from app.modules.wip import blueprint
from app.modules.wip.models import (
    NotificationPublication,
    NotificationPublicationContact,
)
from app.modules.wip.services.newsroom.publication_notification_service import (
    PublicationNotificationError,
    PublicationNotificationService,
)
from app.modules.wip.services.pr_notifications import absolute_url_for

from ._common import get_secondary_menu

# --------------------------------------------------------------------
# Émetteur
# --------------------------------------------------------------------


@blueprint.route("/newsroom/notifications-publication")
def notifications_publication_index():
    user = cast(User, current_user)
    if user.is_anonymous:
        return redirect(url_for("security.login"))

    stmt = (
        select(NotificationPublication)
        .where(NotificationPublication.owner_id == user.id)
        .options(selectinload(NotificationPublication.contacts))
        .order_by(NotificationPublication.notified_at.desc())
    )
    notifications = list(db.session.execute(stmt).scalars())
    return render_template(
        "wip/pages/publication_notifications_index.j2",
        title="Notifications de publication envoyées",
        notifications=notifications,
        menus={"secondary": get_secondary_menu("newsroom")},
    )


@blueprint.route("/newsroom/notifications-publication/new", methods=["GET", "POST"])
def notifications_publication_new():
    user = cast(User, current_user)
    if user.is_anonymous:
        return redirect(url_for("security.login"))

    if request.method == "POST":
        return _handle_free_form_post(journalist=user)

    return render_template(
        "wip/pages/publication_notification_new.j2",
        title="Notifier une publication",
        users=_list_searchable_users(exclude_user_id=user.id),
        menus={"secondary": get_secondary_menu("newsroom")},
    )


def _handle_free_form_post(*, journalist: User) -> Response:
    recipient_ids = request.form.getlist("recipient_ids")
    if not recipient_ids:
        flash("Veuillez sélectionner au moins un destinataire.", "error")
        return redirect(url_for("wip.notifications_publication_new"))

    id_ints: list[int] = []
    for raw in recipient_ids:
        try:
            id_ints.append(int(raw))
        except ValueError:
            continue
    recipients = (
        list(
            db.session.execute(
                select(User).where(User.id.in_(id_ints), User.active)
            ).scalars()
        )
        if id_ints
        else []
    )
    if not recipients:
        flash("Aucun destinataire valide.", "error")
        return redirect(url_for("wip.notifications_publication_new"))

    svc = container.get(PublicationNotificationService)
    try:
        _notif, skipped = svc.notify_free_form(
            journalist=journalist,
            recipients=recipients,
            article_url=request.form.get("article_url", ""),
            article_title=request.form.get("article_title", ""),
            message=request.form.get("message", ""),
            opportunities_url_builder=_opportunities_url_builder,
        )
    except PublicationNotificationError as e:
        flash(str(e), "error")
        return redirect(url_for("wip.notifications_publication_new"))

    _flash_skipped(skipped)
    db.session.commit()
    flash("Notification envoyée.", "success")
    return redirect(url_for("wip.notifications_publication_index"))


# --------------------------------------------------------------------
# Destinataire
# --------------------------------------------------------------------


@blueprint.route("/opportunities/notifications-publication")
def opportunities_notifications_publication():
    user = cast(User, current_user)
    if user.is_anonymous:
        return redirect(url_for("security.login"))

    stmt = (
        select(NotificationPublicationContact)
        .where(NotificationPublicationContact.recipient_user_id == user.id)
        .options(selectinload(NotificationPublicationContact.notification))
        .order_by(NotificationPublicationContact.sent_at.desc())
    )
    contacts = list(db.session.execute(stmt).scalars())
    return render_template(
        "wip/pages/opportunities_publication_notifications.j2",
        title="Notifications de publication reçues",
        contacts=contacts,
        menus={"secondary": get_secondary_menu("opportunities")},
    )


@blueprint.route("/opportunities/notifications-publication/<int:contact_id>")
def opportunities_notification_publication_detail(contact_id: int):
    user = cast(User, current_user)
    if user.is_anonymous:
        return redirect(url_for("security.login"))

    contact = db.session.get(NotificationPublicationContact, contact_id)
    if contact is None or contact.recipient_user_id != user.id:
        flash("Notification introuvable.", "error")
        return redirect(url_for("wip.opportunities_notifications_publication"))

    if contact.read_at is None:
        contact.read_at = datetime.now(UTC)
        db.session.commit()

    return render_template(
        "wip/pages/opportunity_publication_notification.j2",
        title="Notification de publication",
        contact=contact,
        notification=contact.notification,
        menus={"secondary": get_secondary_menu("opportunities")},
    )


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------


def _list_searchable_users(exclude_user_id: int) -> list[User]:
    stmt = (
        select(User)
        .where(and_(User.active, User.id != exclude_user_id))
        .order_by(User.last_name, User.first_name)
    )
    return list(db.session.execute(stmt).scalars())


def _flash_skipped(skipped: list[User]) -> None:
    if not skipped:
        return
    names = ", ".join(u.full_name for u in skipped[:5])
    extra = "" if len(skipped) <= 5 else f" (et {len(skipped) - 5} autre(s))"
    flash(
        f"{len(skipped)} destinataire(s) sauté(s) (plafond anti-spam "
        f"ou notification déjà envoyée récemment) : {names}{extra}.",
        "warning",
    )


def _opportunities_url_builder(
    _notif: NotificationPublication,
) -> str:
    return absolute_url_for("wip.opportunities_notifications_publication")
