# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E-mail notifications around Marketplace offers.

- `notify_emitter_of_application`: new candidacy lands → e-mail owner.
- `notify_applicant_selected` / `notify_applicant_rejected`: owner
  decides on a candidacy → e-mail candidate.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import current_app, url_for

from app.flask.extensions import db
from app.logging import warn
from app.models.auth import User
from app.services.emails import (
    ApplicationRejectedMail,
    ApplicationSelectedMail,
    MissionApplicationMail,
)

if TYPE_CHECKING:
    from app.modules.biz.models import OfferApplication


def notify_emitter_of_application(
    *,
    mission,
    application: OfferApplication,
) -> None:
    """E-mail the offer owner when a new candidacy is submitted.

    Silently skipped if no recipient e-mail can be resolved.
    """
    recipient = _pick_emitter_email(mission)
    if not recipient:
        warn(
            f"No recipient e-mail for offer {mission.id}; "
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


def notify_applicant_selected(
    *, offer, application: OfferApplication
) -> None:
    _notify_applicant_decision(
        offer=offer, application=application, selected=True
    )


def notify_applicant_rejected(
    *, offer, application: OfferApplication
) -> None:
    _notify_applicant_decision(
        offer=offer, application=application, selected=False
    )


def _notify_applicant_decision(
    *, offer, application: OfferApplication, selected: bool
) -> None:
    applicant = db.session.get(User, application.owner_id)
    if applicant is None or not applicant.email:
        warn(
            f"No applicant e-mail for application {application.id}; "
            f"skipping outcome notification"
        )
        return

    emitter = db.session.get(User, offer.owner_id)
    emitter_name = emitter.full_name if emitter else "L'émetteur de l'offre"
    emitter_email = emitter.email if emitter else "contact@aipress24.com"

    offer_url = _absolute_offer_url(offer)

    if selected:
        mail = ApplicationSelectedMail(
            sender="contact@aipress24.com",
            recipient=applicant.email,
            sender_mail=emitter_email,
            offer_title=offer.title,
            offer_url=offer_url,
            emitter_name=emitter_name,
        )
    else:
        mail = ApplicationRejectedMail(
            sender="contact@aipress24.com",
            recipient=applicant.email,
            sender_mail=emitter_email,
            offer_title=offer.title,
            offer_url=offer_url,
        )
    mail.send()


def _pick_emitter_email(offer) -> str:
    if getattr(offer, "contact_email", ""):
        return offer.contact_email
    owner = db.session.get(User, offer.owner_id)
    if owner is not None and owner.email:
        return owner.email
    return ""


def _absolute_profile_url(user: User) -> str:
    try:
        path = url_for("swork.member", id=user.id)
    except Exception:  # noqa: BLE001
        path = f"/swork/members/{user.id}"
    return _absolutize(path)


def _absolute_applications_url(offer) -> str:
    endpoint, fallback = _dashboard_for(offer)
    try:
        return _absolutize(url_for(endpoint, id=offer.id))
    except Exception:  # noqa: BLE001
        return _absolutize(fallback)


def _absolute_offer_url(offer) -> str:
    endpoint, fallback = _detail_for(offer)
    try:
        return _absolutize(url_for(endpoint, id=offer.id))
    except Exception:  # noqa: BLE001
        return _absolutize(fallback)


def _dashboard_for(offer) -> tuple[str, str]:
    kind = getattr(offer, "type", "mission_offer")
    match kind:
        case "project_offer":
            return (
                "biz.projects_applications",
                f"/biz/projects/{offer.id}/applications",
            )
        case "job_offer":
            return (
                "biz.jobs_applications",
                f"/biz/jobs/{offer.id}/applications",
            )
        case _:
            return (
                "biz.missions_applications",
                f"/biz/missions/{offer.id}/applications",
            )


def _detail_for(offer) -> tuple[str, str]:
    kind = getattr(offer, "type", "mission_offer")
    match kind:
        case "project_offer":
            return ("biz.projects_detail", f"/biz/projects/{offer.id}")
        case "job_offer":
            return ("biz.jobs_detail", f"/biz/jobs/{offer.id}")
        case _:
            return ("biz.missions_detail", f"/biz/missions/{offer.id}")


def _absolutize(path: str) -> str:
    domain = str(current_app.config.get("SERVER_NAME") or "aipress24.com")
    protocol = "http" if domain.startswith("127.") else "https"
    return f"{protocol}://{domain}{path}"
