# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Ticket #0362: the destinataire learns, by bell and by mail, that the
commanditaire has validated or cancelled the commande addressed to them."""

from __future__ import annotations

from typing import TYPE_CHECKING

from svcs.flask import container

from app.logging import report_failure
from app.services.emails import CommandeStatusNotificationMail
from app.services.notifications import NotificationService

if TYPE_CHECKING:
    from app.models.auth import User
    from app.modules.wip.models import Commande


def notify_destinataire(
    commande: Commande, commanditaire: User, commande_url: str
) -> None:
    """Bell and mail to the destinataire about the commande's new status.

    A commande without destinataire has nobody to tell. A failed
    notification is reported, not raised: the status change stands. The
    bell is only added to the session; the caller commits it.
    """
    destinataire = commande.destinataire
    if destinataire is None:
        return

    status_label = commande.status_label.lower()
    message = (
        f"La commande « {commande.titre} » qui vous est adressée a été "
        f"{status_label} par {commanditaire.full_name}."
    )
    try:
        container.get(NotificationService).post(destinataire, message, url=commande_url)
    except Exception as exc:
        report_failure("commande status: in-app notification failed", exc)

    if not destinataire.email:
        return
    org = commanditaire.organisation
    try:
        CommandeStatusNotificationMail(
            sender="contact@aipress24.com",
            recipient=destinataire.email,
            sender_mail=commanditaire.email,
            subject=f"[Aipress24] Une commande qui vous est adressée a été {status_label}",
            status_label=status_label,
            commanditaire_full_name=commanditaire.full_name,
            commanditaire_organisation=(org.bw_name or org.name) if org else "",
            commande_title=commande.titre,
            commande_url=commande_url,
        ).send()
    except Exception as exc:
        report_failure(f"commande status mail failed (commande {commande.id})", exc)
