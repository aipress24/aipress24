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

from typing import TYPE_CHECKING, Any

from svcs.flask import container

from app.flask.extensions import db
from app.logging import report_failure
from app.models.lifecycle import PublicationStatus
from app.modules.wip.models.newsroom.commande import Commande
from app.services.notifications import NotificationService

if TYPE_CHECKING:
    from app.models.auth import User
    from app.modules.wip.models.newsroom.sujet import Sujet


# ── Pure decision helpers ───────────────────────────────────────────
#
# The acceptance flow has three pure pieces : the precondition check
# (org match + sujet status), the Commande field mapping from the
# sujet, and the « should we notify the author » skip rule. Each is
# extracted so the rules can be unit-tested at microsecond speed
# without a DB fixture. The rédac-chef check stays in the orchestrator
# below (it needs a DB lookup).


def validate_basic_acceptance(
    *,
    accepter_org_id: int | None,
    sujet_media_id: int | None,
    sujet_status: Any,
) -> None:
    """Raise `ValueError` if the basic preconditions for accepting a
    sujet aren't met. Doesn't cover the rédac-chef check — that's
    DB-coupled and lives in the orchestrator.

    Two rules :

    1. The accepter must belong to the target media organisation
       (`accepter.organisation_id == sujet.media_id`). Otherwise an
       outsider can hijack the sujet (security VULN-001 prequel).
    2. The sujet must be in PUBLIC status — a DRAFT sujet hasn't been
       offered yet, and an ARCHIVED one has already been accepted
       (or refused). Pin so the orchestrator can't fire twice.
    """
    if accepter_org_id != sujet_media_id:
        msg = (
            "User is not authorized to accept this sujet — must be a "
            "member of the target media organisation"
        )
        raise ValueError(msg)

    if sujet_status != PublicationStatus.PUBLIC:
        msg = f"Cannot accept sujet: not in PUBLIC status (got {sujet_status})"
        raise ValueError(msg)


def build_commande_payload(sujet: Sujet, accepter_id: int) -> dict:
    """Map a sujet onto the field set for a new Commande row.

    Pure — no DB ; the orchestrator passes the result to
    `Commande(**payload)`. Encodes the business rules :

    - `owner_id` = the sujet's author (the journalist who proposed it
      and will execute the commande — the « Auteur ») ;
      `commanditaire_id` = the accepter (the rédac chef who
      commissioned it). Bug #0225 : the commande must surface in BOTH
      newsrooms — the journalist sees it as owner, the rédac chef as
      commanditaire (see `CommandeDataSource`). Before #0225 both were
      the accepter, so the journalist never saw their accepted sujet.
    - `media_id` mirrors the sujet's, so the new commande lives in
      the rédac chef's own newsroom.
    - `brief` defaults to "" when the author didn't fill one (NOT
      NULL column on Commande).
    - `status = DRAFT` — the rédac chef tweaks before publishing.
    - `date_bouclage` AND `date_paiement` default to the sujet's
      `date_parution_prevue` so the NOT-NULL columns get a sensible
      starting point ; the rédac chef can adjust before publishing.
    """
    return {
        "owner_id": sujet.owner_id,
        "media_id": sujet.media_id,
        "commanditaire_id": accepter_id,
        "titre": sujet.titre,
        "contenu": sujet.contenu,
        "brief": sujet.brief or "",
        "status": PublicationStatus.DRAFT,
        "date_limite_validite": sujet.date_limite_validite,
        "date_parution_prevue": sujet.date_parution_prevue,
        "date_bouclage": sujet.date_parution_prevue,
        "date_paiement": sujet.date_parution_prevue,
    }


def is_notification_eligible(author: Any) -> bool:
    """Return True iff `author` should receive the acceptance cloche.

    Skips the anonymous / missing-author cases up-front so the
    orchestrator can return without touching the notification
    service."""
    if author is None:
        return False
    return not getattr(author, "is_anonymous", False)


# ── Orchestrators ───────────────────────────────────────────────────


def accept_sujet_as_commande(sujet: Sujet, accepter: User) -> Commande:
    """Materialise a Commande from `sujet`, archive the sujet.

    Args:
        sujet: the PUBLIC sujet to accept. Must be in PUBLIC status.
        accepter: the user accepting (= the rédac chef). Their
            organisation_id must match `sujet.media_id` AND they must
            qualify as rédac chef of that organisation (security
            VULN-001 — without the rédac chef check, any ordinary
            journalist at the target media could hijack the sujet).

    Returns:
        the newly-created (and flushed) Commande row.

    Raises:
        ValueError: if the accepter isn't authorised or the sujet
            isn't in PUBLIC status.
    """
    validate_basic_acceptance(
        accepter_org_id=accepter.organisation_id,
        sujet_media_id=sujet.media_id,
        sujet_status=sujet.status,
    )

    # Lazy import to keep the auth helper out of the cold-start path.
    from app.modules.wip.crud.cbvs.sujets import _is_redac_chef_of_org

    if not _is_redac_chef_of_org(accepter, sujet.media_id):
        msg = (
            "User is not authorized to accept this sujet — only the "
            "rédac chef of the target media may accept (#0132 pt 1)"
        )
        raise ValueError(msg)

    commande = Commande(**build_commande_payload(sujet, accepter.id))
    db.session.add(commande)
    db.session.flush()

    sujet.status = PublicationStatus.ARCHIVED  # type: ignore[assignment]

    return commande


def refuse_sujet(sujet: Sujet, refuser: User) -> None:
    """Refuse a received sujet — archive it WITHOUT creating a Commande.

    Ticket #0225 : the rédac chef may refuse a proposal, not only accept
    it. Same authorization gate as acceptance (VULN-001) : only the rédac
    chef of the target media, and only a PUBLIC (received) sujet.

    Raises:
        ValueError: if the refuser isn't authorised or the sujet isn't in
            PUBLIC status.
    """
    validate_basic_acceptance(
        accepter_org_id=refuser.organisation_id,
        sujet_media_id=sujet.media_id,
        sujet_status=sujet.status,
    )

    # Lazy import to keep the auth helper out of the cold-start path.
    from app.modules.wip.crud.cbvs.sujets import _is_redac_chef_of_org

    if not _is_redac_chef_of_org(refuser, sujet.media_id):
        msg = (
            "User is not authorized to refuse this sujet — only the "
            "rédac chef of the target media may refuse (#0225)"
        )
        raise ValueError(msg)

    sujet.status = PublicationStatus.ARCHIVED  # type: ignore[assignment]


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
    if not is_notification_eligible(author):
        return
    try:
        message = (
            f"Votre sujet « {sujet_title} » a été accepté par {accepter.full_name}."
        )
        container.get(NotificationService).post(author, message, url=commande_url)
    except Exception as exc:
        report_failure("sujet acceptance: in-app notification failed", exc)


def notify_author_of_sujet_refusal(
    *,
    author: User,
    refuser: User,
    sujet_title: str,
    sujet_url: str,
) -> None:
    """Post an in-app notification to the sujet author when the rédac
    chef refuses their proposal (ticket #0225)."""
    if not is_notification_eligible(author):
        return
    try:
        message = (
            f"Votre sujet « {sujet_title} » a été refusé par {refuser.full_name}."
        )
        container.get(NotificationService).post(author, message, url=sujet_url)
    except Exception as exc:
        report_failure("sujet refusal: in-app notification failed", exc)
