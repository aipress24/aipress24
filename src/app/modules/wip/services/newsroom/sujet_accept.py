# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Ticket #0132 part 3 — « Accepter » a Sujet → create a Commande.

Workflow expected by Erick (2026-05-22) :

    Author publishes Sujet → arrives in target media's NEWSROOM/Sujets
    list. Rédac chef opens it, clicks « Accepter » → a Commande is
    materialised in NEWSROOM/Commandes (with the sujet's title and
    body, owned by the rédac chef who accepted, media_id pinned to
    their org). The sujet itself moves to ARCHIVED so it stops
    showing up as « new » and the action can't fire twice. The
    author gets a cloche + email notification so they know their
    proposal has been picked up.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from svcs.flask import container

from app.flask.extensions import db
from app.logging import warn
from app.models.lifecycle import PublicationStatus
from app.modules.wip.models.newsroom.commande import Commande
from app.services.notifications import NotificationService

if TYPE_CHECKING:
    from app.models.auth import User
    from app.modules.wip.models.newsroom.sujet import Sujet


def accept_sujet_as_commande(sujet: Sujet, accepter: User) -> Commande:
    """Materialise a Commande from `sujet`, archive the sujet.

    Args:
        sujet: the PUBLIC sujet to accept. Must be in PUBLIC status.
        accepter: the user accepting (= the rédac chef). Their
            organisation_id must match `sujet.media_id`.

    Returns:
        the newly-created (and flushed) Commande row.

    Raises:
        ValueError: if the accepter isn't authorised or the sujet
            isn't in PUBLIC status.
    """
    if accepter.organisation_id != sujet.media_id:
        msg = (
            "User is not authorized to accept this sujet — must be a "
            "member of the target media organisation"
        )
        raise ValueError(msg)

    if sujet.status != PublicationStatus.PUBLIC:
        msg = f"Cannot accept sujet: not in PUBLIC status (got {sujet.status})"
        raise ValueError(msg)

    commande = Commande(
        owner_id=accepter.id,
        media_id=sujet.media_id,
        commanditaire_id=accepter.id,
        titre=sujet.titre,
        contenu=sujet.contenu,
        brief=sujet.brief or "",
        status=PublicationStatus.DRAFT,
        # Mirror the sujet's deadlines / publication target onto the
        # new commande so the rédac chef doesn't have to retype them.
        date_limite_validite=sujet.date_limite_validite,
        date_parution_prevue=sujet.date_parution_prevue,
        # Commande requires a `date_bouclage` and `date_paiement` (NOT
        # NULL columns) ; default both to the sujet's publication
        # date as a reasonable starting point — the rédac chef can
        # adjust before publishing the commande.
        date_bouclage=sujet.date_parution_prevue,
        date_paiement=sujet.date_parution_prevue,
    )
    db.session.add(commande)
    db.session.flush()

    sujet.status = PublicationStatus.ARCHIVED  # type: ignore[assignment]

    return commande


def notify_author_of_sujet_acceptance(
    *,
    author: User,
    accepter: User,
    sujet_title: str,
    commande_url: str,
) -> None:
    """Post an in-app notification to the sujet author when the rédac
    chef accepts their proposal (ticket #0132 part 3).

    The mail side-effect lives in the route handler — this helper is
    in-app only so a flaky transport doesn't undo the state change.
    """
    if author is None or getattr(author, "is_anonymous", False):
        return
    try:
        message = (
            f"Votre sujet « {sujet_title} » a été accepté par {accepter.full_name}."
        )
        container.get(NotificationService).post(author, message, url=commande_url)
    except Exception as exc:
        warn(f"sujet acceptance: in-app notification failed: {exc}")
