# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E-mail + in-app notifications around Marketplace offers.

- `notify_emitter_of_application`: new candidacy lands → e-mail owner.
- `notify_applicant_selected` / `notify_applicant_rejected`: owner
  decides on a candidacy → e-mail + in-app cloche to the candidate.
  Per Erick #0199 + #0200 both channels carry the optional free-text
  `decision_message` the emitter wrote on the dashboard.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from flask import current_app, url_for
from svcs.flask import container

from app.flask.extensions import db
from app.logging import warn
from app.models.auth import User
from app.services.emails import (
    ApplicationRejectedMail,
    ApplicationSelectedMail,
    MissionApplicationMail,
)
from app.services.notifications import NotificationService

if TYPE_CHECKING:
    from app.modules.biz.models import OfferApplication


def notify_emitter_of_application(
    *,
    mission,
    application: OfferApplication,
) -> None:
    """Notify the offer owner when a new candidacy is submitted, by
    BOTH in-app cloche and e-mail.

    Bug #0200 — Erick : the emitter must be alerted on the bell, not
    just by e-mail. The cloche links to the applications dashboard so
    the emitter can accept / refuse straight away. The mail is still
    skipped (with a warning) when no recipient address can be resolved.
    """
    applicant = db.session.get(User, application.owner_id)
    if applicant is None:
        return

    # In-app cloche to the offer owner — fired regardless of e-mail
    # validity, non-fatal (a notification glitch must not block the mail).
    emitter = db.session.get(User, mission.owner_id)
    if emitter is not None:
        message = (
            f"Nouvelle candidature de {applicant.full_name} "
            f"pour « {mission.title} »."
        )
        with contextlib.suppress(Exception):
            container.get(NotificationService).post(
                emitter, message, url=_absolute_applications_url(mission)
            )

    recipient = _pick_emitter_email(mission)
    if not recipient:
        warn(
            f"No recipient e-mail for offer {mission.id}; "
            f"skipping application notification e-mail"
        )
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


def notify_applicant_selected(*, offer, application: OfferApplication) -> None:
    _notify_applicant_decision(offer=offer, application=application, selected=True)


def notify_applicant_rejected(*, offer, application: OfferApplication) -> None:
    _notify_applicant_decision(offer=offer, application=application, selected=False)


def _notify_applicant_decision(
    *, offer, application: OfferApplication, selected: bool
) -> None:
    applicant = db.session.get(User, application.owner_id)
    if applicant is None:
        warn(
            f"No applicant for application {application.id}; "
            f"skipping outcome notification"
        )
        return

    emitter = db.session.get(User, offer.owner_id)
    emitter_name = emitter.full_name if emitter else "L'émetteur de l'offre"
    emitter_email = emitter.email if emitter else "contact@aipress24.com"

    offer_url = _absolute_offer_url(offer)
    decision_message = getattr(application, "decision_message", "") or ""

    # In-app cloche (#0199 + #0200 explicitly require it alongside the
    # mail). The applicant sees both regardless of e-mail validity ;
    # NotificationService failures are non-fatal — we still try the mail.
    verb = "sélectionnée" if selected else "non retenue"
    in_app_message = (
        f"Votre candidature pour « {offer.title} » a été {verb} par {emitter_name}."
    )
    if decision_message:
        in_app_message += f" Message : {decision_message}"
    with contextlib.suppress(Exception):
        container.get(NotificationService).post(
            applicant, in_app_message, url=offer_url
        )

    if not applicant.email:
        return

    if selected:
        mail = ApplicationSelectedMail(
            sender="contact@aipress24.com",
            recipient=applicant.email,
            sender_mail=emitter_email,
            offer_title=offer.title,
            offer_url=offer_url,
            emitter_name=emitter_name,
            decision_message=decision_message,
        )
    else:
        mail = ApplicationRejectedMail(
            sender="contact@aipress24.com",
            recipient=applicant.email,
            sender_mail=emitter_email,
            offer_title=offer.title,
            offer_url=offer_url,
            emitter_name=emitter_name,
            decision_message=decision_message,
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
    except Exception:
        path = f"/swork/members/{user.id}"
    return _absolutize(path)


def _absolute_applications_url(offer) -> str:
    endpoint, fallback = _dashboard_for(offer)
    try:
        return _absolutize(url_for(endpoint, id=offer.id))
    except Exception:
        return _absolutize(fallback)


def _absolute_offer_url(offer) -> str:
    endpoint, fallback = _detail_for(offer)
    try:
        return _absolutize(url_for(endpoint, id=offer.id))
    except Exception:
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
