# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tâche périodique de livraison des notifications groupées."""

from __future__ import annotations

from loguru import logger

from app.dramatiq.scheduler import crontab
from app.flask.extensions import db
from app.services.notifications import deliver_due_notifications


@crontab("7-57/10 * * * *")
def deliver_grouped_notifications() -> None:
    """Drainer la file d'attente toutes les dix minutes.

    Le pas est plus fin que la fenêtre de regroupement pour que le
    retard ajouté à la livraison reste petit devant elle.

    Le créneau évite HH:00 et HH:15, déjà pris par la réputation et la
    reconstruction de l'index de recherche : trois tâches lourdes à la
    même minute se gênent pour rien.
    """
    delivered = deliver_due_notifications(db.session)
    db.session.commit()
    if delivered:
        logger.info(f"cron: delivered {delivered} grouped notification(s)")


@crontab("2 * * * *")
def send_event_reminders() -> None:
    """Rappeler la veille les événements du lendemain.

    Toutes les heures, et non une fois par jour à 09:00 : c'est le
    registre d'envoi qui garantit l'unicité, pas la rareté du
    déclenchement. Un tour manqué se rattrape ainsi au suivant, alors
    qu'un crontab quotidien perdrait la journée.

    À la minute 2, pour ne pas se disputer l'heure juste avec la
    réputation.
    """
    from app.modules.events.reminders import send_due_reminders

    sent = send_due_reminders(db.session)
    db.session.commit()
    if sent:
        logger.info(f"cron: sent {sent} event reminder(s)")
