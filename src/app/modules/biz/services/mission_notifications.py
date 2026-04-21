# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Notify a mission emitter when a new application is submitted."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import current_app, url_for

from app.flask.extensions import db
from app.logging import warn
from app.models.auth import User
from app.services.emails import MissionApplicationMail

if TYPE_CHECKING:
    from app.modules.biz.models import MissionApplication, MissionOffer


def notify_emitter_of_application(
    *,
    mission: MissionOffer,
    application: MissionApplication,
) -> None:
    """Send an e-mail to the mission emitter when a new application lands.

    Silently skipped if no recipient e-mail can be resolved.
    """
    recipient = _pick_recipient_email(mission)
    if not recipient:
        warn(
            f"No recipient e-mail for mission {mission.id}; "
            f"skipping application notification"
        )
        return

    applicant = db.session.get(User, application.owner_id)
    if applicant is None:
        return

    mail = MissionApplicationMail(
        sender="contact@aipress24.com",
        recipient=recipient,
        sender_mail=applicant.email,
        sender_full_name=applicant.full_name,
        mission_title=mission.title,
        applicant_message=application.message,
        applicant_profile_url=_absolute_profile_url(applicant),
        applications_url=_absolute_applications_url(mission),
    )
    mail.send()


def _pick_recipient_email(mission: MissionOffer) -> str:
    if mission.contact_email:
        return mission.contact_email
    owner = db.session.get(User, mission.owner_id)
    if owner is not None and owner.email:
        return owner.email
    return ""


def _absolute_profile_url(user: User) -> str:
    try:
        path = url_for("swork.member", id=user.id)
    except Exception:  # noqa: BLE001
        path = f"/swork/members/{user.id}"
    return _absolutize(path)


def _absolute_applications_url(mission: MissionOffer) -> str:
    try:
        path = url_for("biz.missions_applications", id=mission.id)
    except Exception:  # noqa: BLE001
        path = f"/biz/missions/{mission.id}/applications"
    return _absolutize(path)


def _absolutize(path: str) -> str:
    domain = str(current_app.config.get("SERVER_NAME") or "aipress24.com")
    protocol = "http" if domain.startswith("127.") else "https"
    return f"{protocol}://{domain}{path}"
