# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Accréditation à un événement.

Seul écrivain de `evt_accreditation` : le modèle ne connaît aucune
règle de transition, elles vivent toutes ici. Les règles portent les
numéros de `specs/events-accreditations.md` §5.

État du chantier (lot L1) : la table de stockage est basculée et l'API
du workflow est en place, mais les vues appellent encore l'ancien
couple `add_participant` / `remove_participant`, qui accrédite
directement. Le parcours « demande puis décision » est câblé au lot L2,
le ciblage au L3, l'écran organisateur au L4.
"""

from __future__ import annotations

import arrow
import sqlalchemy as sa

from app.enums import RoleEnum
from app.flask.extensions import db
from app.models.auth import User
from app.models.lifecycle import PublicationStatus

from .models import Accreditation, AccreditationStatus, EventPost

# Statuts qui bloquent une nouvelle demande (RG-03). `WITHDRAWN` n'y
# est pas : un membre qui s'est désinscrit peut revenir.
_BLOCKS_A_NEW_REQUEST = (
    AccreditationStatus.REQUESTED,
    AccreditationStatus.ACCEPTED,
    AccreditationStatus.REJECTED,
)


class AccreditationClosedError(Exception):
    """L'événement n'accepte pas (ou plus) de demande.

    Levée par `request_accreditation` quand l'événement n'est pas
    publié, ou que sa date de début est passée (RG-04). La vue la
    traduit en `409 Conflict`.
    """


#
# Lecture
#
def get_accreditation(event: EventPost, user: User) -> Accreditation | None:
    """La ligne du couple (événement, membre), s'il y en a une."""
    stmt = sa.select(Accreditation).where(
        Accreditation.event_id == event.id,
        Accreditation.user_id == user.id,
    )
    return db.session.scalars(stmt).one_or_none()


def get_accreditations_by_status(
    event: EventPost, status: AccreditationStatus
) -> list[Accreditation]:
    """Les lignes d'un statut donné, dans l'ordre des demandes.

    Alimente les trois onglets de l'écran « Accréditer ».
    """
    stmt = (
        sa.select(Accreditation)
        .where(
            Accreditation.event_id == event.id,
            Accreditation.status == status,
        )
        .order_by(Accreditation.requested_at)
    )
    return list(db.session.scalars(stmt))


def get_participants(
    event: EventPost,
    order_by=None,
    limit: int = 0,
) -> list[User]:
    """Les membres accrédités à un événement.

    RG-11 : seules les lignes `ACCEPTED` comptent. Une demande en
    cours, un refus ou une désinscription ne font pas un participant.

    Args:
        event: The event to get participants for.
        order_by: Column or tuple of columns to order by.
        limit: Maximum number of participants to return (0 = no limit).
    """
    if not isinstance(event, EventPost):
        msg = f"Expected EventPost, got {type(event)}"
        raise TypeError(msg)

    ids = sa.select(Accreditation.user_id).where(
        Accreditation.event_id == event.id,
        Accreditation.status == AccreditationStatus.ACCEPTED,
    )
    stmt = sa.select(User).where(User.id.in_(ids))

    if order_by is not None:
        if isinstance(order_by, tuple):
            stmt = stmt.order_by(*order_by)
        else:
            stmt = stmt.order_by(order_by)

    if limit:
        stmt = stmt.limit(limit)

    return list(db.session.scalars(stmt))


def accredited_event_ids(user_ids: list[int]) -> sa.Select:
    """Sous-requête des événements auxquels ces membres sont accrédités.

    Partagée par le bloc « Votre agenda » et par la colonne de droite
    du Business Wall, qui posaient la même question à l'ancienne table.
    """
    return sa.select(Accreditation.event_id).where(
        Accreditation.user_id.in_(user_ids),
        Accreditation.status == AccreditationStatus.ACCEPTED,
    )


#
# Demande et retrait, côté membre
#
def request_accreditation(event: EventPost, user: User) -> Accreditation:
    """Demander une accréditation (RG-03).

    Idempotent (RG-10) : si une ligne bloquante existe déjà, elle est
    renvoyée telle quelle. Deux clics ne créent qu'une demande, et une
    re-demande après refus ne rouvre rien — seul l'organisateur le peut
    (RG-13).

    Raises:
        AccreditationClosedError: événement non publié, ou déjà commencé.
    """
    _require_open(event)

    accreditation = get_accreditation(event, user)
    if accreditation is not None:
        if accreditation.status in _BLOCKS_A_NEW_REQUEST:
            return accreditation
        # WITHDRAWN : le membre revient sur sa décision.
        accreditation.status = AccreditationStatus.REQUESTED
        accreditation.requested_at = arrow.utcnow()
        accreditation.decided_at = None
        accreditation.decided_by_id = None
        return accreditation

    accreditation = Accreditation(
        event_id=event.id,
        user_id=user.id,
        status=AccreditationStatus.REQUESTED,
    )
    db.session.add(accreditation)
    return accreditation


def withdraw_accreditation(event: EventPost, user: User) -> Accreditation | None:
    """Annuler sa demande, ou se désinscrire (RG-08).

    Les deux gestes sont le même côté membre. Renvoie `None` si le
    membre n'avait rien demandé — un retrait sans demande est un no-op,
    pas une erreur (RG-10).
    """
    accreditation = get_accreditation(event, user)
    if accreditation is None:
        return None

    accreditation.status = AccreditationStatus.WITHDRAWN
    return accreditation


#
# Décision, côté organisateur
#
def accept_accreditations(
    event: EventPost, user_ids: list[int], decided_by: User
) -> int:
    """Accréditer une sélection (RG-06), ou rouvrir un refus (RG-13).

    Renvoie le nombre de lignes touchées.
    """
    return _decide(event, user_ids, AccreditationStatus.ACCEPTED, decided_by)


def reject_accreditations(
    event: EventPost, user_ids: list[int], decided_by: User
) -> int:
    """Refuser une sélection (RG-07), ou retirer une accréditation déjà
    accordée (RG-09). Renvoie le nombre de lignes touchées."""
    return _decide(event, user_ids, AccreditationStatus.REJECTED, decided_by)


def _decide(
    event: EventPost,
    user_ids: list[int],
    status: AccreditationStatus,
    decided_by: User,
) -> int:
    """Une seule requête, quel que soit le nombre de destinataires.

    L'écran organisateur accrédite par lot ; une requête par ligne ne
    passerait pas l'échelle sur un salon à plusieurs centaines de
    demandes.
    """
    if not user_ids:
        return 0

    stmt = (
        sa.update(Accreditation)
        .where(
            Accreditation.event_id == event.id,
            Accreditation.user_id.in_(user_ids),
        )
        .values(
            status=status,
            decided_at=arrow.utcnow(),
            decided_by_id=decided_by.id,
        )
    )
    result = db.session.execute(stmt, execution_options={"synchronize_session": False})
    db.session.expire_all()
    return result.rowcount


def _require_open(event: EventPost) -> None:
    if event.status != PublicationStatus.PUBLIC:
        msg = "Cet événement n'est pas publié."
        raise AccreditationClosedError(msg)
    if event.start_datetime is not None and event.start_datetime <= arrow.utcnow():
        msg = "Cet événement a commencé ; les demandes sont closes."
        raise AccreditationClosedError(msg)


#
# Compatibilité — parcours actuel, jusqu'au lot L2
#
def _is_user_in(user_id, participant_ids) -> bool:
    """Pure predicate: True iff `user_id` is in `participant_ids`.

    Extracted for testability (functional core). `participant_ids` may be any
    iterable of ids; `user_id` is compared by equality.
    """
    if user_id is None:
        return False
    return any(pid == user_id for pid in participant_ids)


def is_participant(event: EventPost, user: User) -> bool:
    """True if `user` is accredited to `event`."""
    accreditation = get_accreditation(event, user)
    return (
        accreditation is not None
        and accreditation.status == AccreditationStatus.ACCEPTED
    )


def add_participant(event: EventPost, user: User) -> bool:
    """Accréditer directement, sans passer par une demande.

    C'est le parcours livré aujourd'hui : le membre s'accrédite lui-même
    d'un clic. Il disparaît au lot L2, remplacé par
    `request_accreditation` et la décision de l'organisateur.

    Returns True iff the member was not already accredited.
    """
    if is_participant(event, user):
        return False

    accreditation = get_accreditation(event, user)
    if accreditation is None:
        accreditation = Accreditation(event_id=event.id, user_id=user.id)
        db.session.add(accreditation)
    accreditation.status = AccreditationStatus.ACCEPTED
    accreditation.decided_at = arrow.utcnow()
    return True


def remove_participant(event: EventPost, user: User) -> bool:
    """Retirer son accréditation. Returns True iff there was one."""
    accreditation = get_accreditation(event, user)
    if accreditation is None or accreditation.status != AccreditationStatus.ACCEPTED:
        return False

    accreditation.status = AccreditationStatus.WITHDRAWN
    return True


def can_user_accredit(user: User, event: EventPost) -> bool:
    """Whether `user` is allowed to self-accredit to `event`.

    Bug 0127: accreditation reserved to journalists (`RoleEnum.PRESS_MEDIA`).

    RG-05 demande de lever cette restriction et de ne filtrer que sur
    `event.audience`. Elle ne peut pas l'être ici : sans le ciblage
    (lot L3) ni la modération (lot L4), lever le filtre ouvrirait
    l'inscription à tout le monde, immédiate et sans recours pour
    l'organisateur — pire que l'état actuel. Elle est reportée au lot
    L3, où le ciblage la remplace.
    """
    del event  # le ciblage arrive au lot L3
    return user.has_role(RoleEnum.PRESS_MEDIA)
