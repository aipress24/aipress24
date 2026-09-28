# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Ticket #0362: the destinataire learns, by bell and by mail, that the
commanditaire has validated the commande addressed to them."""

from __future__ import annotations

from typing import TYPE_CHECKING

from svcs.flask import container

from app.logging import report_failure
from app.services.emails import CommandeValidationNotificationMail
from app.services.notifications import NotificationService

if TYPE_CHECKING:
    from app.models.auth import User
    from app.modules.wip.models import Commande


def notify_destinataire_of_validation(
    commande: Commande, validator: User, commande_url: str
) -> None:
    """Bell and mail to the destinataire of a validated commande.

    A failed notification is reported, not raised: the validation stands.
    The bell is only added to the session; the caller commits it.
    """
    destinataire = commande.destinataire
    if destinataire is None:
        msg = f"Commande {commande.id} validated without a destinataire"
        raise ValueError(msg)

    message = (
        f"Votre commande « {commande.titre} » a été validée par {validator.full_name}."
    )
    try:
        container.get(NotificationService).post(destinataire, message, url=commande_url)
    except Exception as exc:
        report_failure("commande validation: in-app notification failed", exc)

    if not destinataire.email:
        return
    org = validator.organisation
    try:
        CommandeValidationNotificationMail(
            sender="contact@aipress24.com",
            recipient=destinataire.email,
            sender_mail=validator.email,
            validator_full_name=validator.full_name,
            validator_organisation=(org.bw_name or org.name) if org else "",
            commande_title=commande.titre,
            commande_url=commande_url,
        ).send()
    except Exception as exc:
        report_failure(f"commande validation mail failed (commande {commande.id})", exc)
