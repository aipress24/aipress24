# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Qui relit les événements d'une organisation — `REL-02`, `REL-03`.

La spécification nomme « BW Master » et « BW Deputy Master ». **Ces
rôles n'existent pas** : le dépôt connaît `BW_OWNER`, `BWMi`, `BWPRi`,
`BWMe` et `BWPRe`, et sa notion d'habilitation est une *mission*
accordée sur le Business Wall — `PermissionType.EVENTS` pour ce qui
touche aux événements. C'est elle qui gouverne déjà l'accès aux écrans
« Cibler » et « Accréditer » (lot L4).

Le relecteur est donc « qui peut décider des événements de cette
organisation », ce qui est exactement ce que la règle décrit en
d'autres mots. Inventer un troisième vocabulaire pour dire la même
chose aurait coûté un modèle de rôles de plus.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from flask import g

from app.flask.extensions import db
from app.models.auth import User
from app.modules.bw.bw_activation.models.role import (
    InvitationStatus,
    PermissionType,
    RoleAssignment,
    RolePermission,
)
from app.modules.bw.bw_activation.user_utils import (
    get_active_business_wall_for_organisation,
)

if TYPE_CHECKING:
    from app.models.organisation import Organisation


def review_required(organisation: Organisation | None) -> bool:
    """La relecture est-elle exigée par cette organisation ? (REL-03)

    Deux cas répondent `False` malgré le drapeau, et pour la même
    raison : **il n'y aurait personne pour relire**, et un événement
    soumis y resterait pour toujours — l'auteur n'a plus la main, et nul
    ne peut la prendre.

    - une organisation absente : un événement sans éditeur n'a pas de
      relecteur ;
    - une organisation dont le Business Wall n'est plus actif : la
      mission « événements » se lit dessus, et sans lui la liste des
      relecteurs est vide. C'est le cas d'un abonnement qui expire
      après que le drapeau a été posé.

    Ce n'est pas une garde défensive mais la règle elle-même : exiger
    une relecture que personne ne peut faire n'est pas une exigence,
    c'est un blocage.
    """
    if organisation is None or not organisation.event_review_required:
        return False
    return bool(reviewers_of(organisation))


def reviewers_of(organisation: Organisation | None) -> list[User]:
    """Les membres habilités à relire les événements de l'organisation.

    Le propriétaire du Business Wall en fait partie de droit — il porte
    toutes les missions — ainsi que toute attribution de rôle acceptée
    qui accorde explicitement la mission « événements ».

    Une seule requête : la liste alimente à la fois la garde d'accès à
    l'écran et les destinataires de NOT-06, qui peut en compter
    plusieurs dizaines dans un grand média.
    """
    bw = (
        get_active_business_wall_for_organisation(organisation)
        if organisation
        else None
    )
    if bw is None:
        return []

    granted = (
        sa.select(RoleAssignment.user_id)
        .join(RolePermission, RolePermission.role_assignment_id == RoleAssignment.id)
        .where(
            RoleAssignment.business_wall_id == bw.id,
            RoleAssignment.invitation_status == InvitationStatus.ACCEPTED.value,
            RolePermission.permission_type == PermissionType.EVENTS.value,
            RolePermission.is_granted.is_(True),
        )
    )
    stmt = sa.select(User).where(sa.or_(User.id == bw.owner_id, User.id.in_(granted)))
    return list(db.session.scalars(stmt))


def is_reviewer(user: User | None, organisation: Organisation | None) -> bool:
    """Ce membre relit-il les événements de cette organisation ?

    Mémoïsé pour la durée de la requête : la liste des actions d'un
    tableau appelle ce prédicat **deux fois par ligne** (le gabarit
    reconstruit le menu une seconde fois dans sa macro), et la réponse
    ne change pas d'une ligne à l'autre. Sans cela, un écran de vingt
    événements coûtait quarante requêtes pour un bouton.
    """
    if user is None or getattr(user, "is_anonymous", True) or organisation is None:
        return False

    if not hasattr(g, "_event_reviewers"):
        g._event_reviewers = {}
    cache = g._event_reviewers
    key = (user.id, organisation.id)
    if key not in cache:
        cache[key] = any(r.id == user.id for r in reviewers_of(organisation))
    return cache[key]


def events_to_review(user: User) -> list:
    """Les événements en attente de la relecture de ce membre (REL-06).

    Une seule requête, et **une seule définition** de ce qu'un relecteur
    voit : l'écran « À relire » et son compteur l'appellent tous les
    deux. C'est la leçon du bug #0132 — un compteur qui a sa propre
    requête finit par annoncer zéro pendant que la liste montre des
    lignes.

    Renvoie une liste vide pour qui n'est relecteur de rien : la liste
    de l'atelier, elle, est filtrée par propriétaire, si bien qu'un
    relecteur ne verrait jamais l'événement d'un collègue sans cet
    écran.
    """
    from app.models.lifecycle import PublicationStatus
    from app.modules.wip.models.eventroom import Event

    organisation = getattr(user, "organisation", None)
    if not is_reviewer(user, organisation):
        return []

    stmt = (
        sa.select(Event)
        .where(Event.publisher_id == organisation.id)
        .where(Event.status == PublicationStatus.PENDING)
        .where(Event.deleted_at.is_(None))
        .order_by(Event.modified_at.desc())
    )
    return list(db.session.scalars(stmt))
