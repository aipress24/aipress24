# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Accréditation à un événement.

Seul écrivain de `evt_accreditation` : le modèle ne connaît aucune
règle de transition, elles vivent toutes ici. Les règles portent les
numéros de `specs/events-accreditations.md` §5.

Le parcours complet est en place : demande (L2), ciblage (L3),
décision de l'organisateur (L4). L'annulation d'un événement ferme tous
ces gestes sans détruire une seule ligne (ANN-05, RG-12).
"""

from __future__ import annotations

import arrow
import sqlalchemy as sa

from app.enums import RoleEnum
from app.flask.extensions import db
from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.modules.kyc.community_role import COMMUNITY_TO_ROLE

from .models import Accreditation, AccreditationStatus, EventPost
from .notifications import (
    notify_accepted,
    notify_rejected,
    notify_request_received,
    notify_withdrawn,
)

# Une audience porte des valeurs de `CommunityEnum` ; l'appartenance
# d'un membre se lit sur ses rôles. Table de correspondance dressée une
# fois, indexée par la valeur telle qu'elle est stockée en JSON.
_ROLE_BY_COMMUNITY_VALUE = {
    community.value: role for community, role in COMMUNITY_TO_ROLE.items()
}

# D'où une décision d'organisateur peut partir, par statut visé.
# Accepter part d'une demande en cours (RG-06) ou d'un refus qu'on
# rouvre (RG-13) ; refuser part d'une demande en cours (RG-07) ou d'une
# accréditation qu'on retire (RG-09). Ni l'une ni l'autre ne sort de
# WITHDRAWN : ce statut n'appartient qu'au membre.
_DECIDABLE_FROM = {
    AccreditationStatus.ACCEPTED: (
        AccreditationStatus.REQUESTED,
        AccreditationStatus.REJECTED,
    ),
    AccreditationStatus.REJECTED: (
        AccreditationStatus.REQUESTED,
        AccreditationStatus.ACCEPTED,
    ),
}

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
def is_signed_in(user) -> bool:
    """Un membre identifié, par opposition à un visiteur.

    Écrit cinq fois à l'identique dans le module avant l'audit du
    2026-09-01. Le `getattr` avec défaut se gardait d'un objet sans
    `is_anonymous`, que ni `User` ni l'utilisateur anonyme de
    Flask-Security ne peuvent être — mais `g.user` vaut `None` hors
    session, et c'est ce cas-là qui compte.
    """
    return user is not None and not user.is_anonymous


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
# Ciblage
#
def in_audience(user: User, audience: list[str]) -> bool:
    """Le membre appartient-il à l'audience visée ? (RG-03a)

    `audience` porte des valeurs de `CommunityEnum` ; l'appartenance
    d'un membre à une communauté est portée par ses **rôles**. La
    correspondance existe déjà : `COMMUNITY_TO_ROLE`.

    Une audience vide est ouverte à tous — c'est le défaut, et il
    préserve le comportement des événements déjà publiés.

    N'utilise délibérément pas `User.first_community()` : elle renvoie
    un `RoleEnum` et non un `CommunityEnum`, et surtout elle lève
    `RuntimeError` pour tout utilisateur sans rôle de communauté — un
    administrateur, un compte de service. `has_role` ne lève jamais.
    """
    if not audience:
        return True
    roles = (_ROLE_BY_COMMUNITY_VALUE.get(value) for value in audience)
    return any(user.has_role(role) for role in roles if role is not None)


def sees_full_content(user: User, event: EventPost) -> bool:
    """Le membre voit-il le contenu de l'annonce ? (RG-02, RG-03b)

    Deux exceptions à l'appartenance, **sur la visibilité seulement** :
    l'organisateur et un administrateur voient toujours le contenu
    intégral, sans quoi le support ne peut plus instruire un
    signalement. Elles n'ouvrent pas le droit de demander une
    accréditation, qui reste conditionné à l'audience.
    """
    if user.id == event.owner_id or user.has_role(RoleEnum.ADMIN):
        return True
    return in_audience(user, event.audience or [])


def sees_access_details(user: User, event: EventPost) -> bool:
    """Le membre voit-il les modalités d'accès ? (MOD-02)

    **Ce n'est pas `sees_full_content`.** Celui-ci dit l'appartenance à
    l'audience, et une audience vide — le cas ordinaire — laisse passer
    tout le site. Y adosser `access_details` publierait le code d'accès
    d'une visioconférence à tout le monde.

    Le seul droit qui compte ici est l'accréditation accordée : c'est
    ce que MOD-02 demande, et ce dont un code d'entrée a besoin.
    L'organisateur voit les siens, évidemment — il les a saisis.
    """
    if not is_signed_in(user):
        return False
    if user.id == event.owner_id:
        return True
    return is_participant(event, user)


def accredited_ids_among(user, event_ids: list[int]) -> set[int]:
    """Parmi ces événements, lesquels le membre est-il accrédité ? (§7.2)

    Une seule requête pour toute une page de liste. Un appel par carte
    en ferait autant qu'il y a d'événements affichés, pour une pastille.
    """
    if not is_signed_in(user) or not event_ids:
        return set()
    stmt = sa.select(Accreditation.event_id).where(
        Accreditation.user_id == user.id,
        Accreditation.event_id.in_(event_ids),
        Accreditation.status == AccreditationStatus.ACCEPTED,
    )
    return set(db.session.scalars(stmt))


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
        PermissionError: le membre n'appartient pas à l'audience visée.
    """
    _require_open(event)
    if not in_audience(user, event.audience or []):
        msg = "Cet événement est réservé à d'autres communautés."
        raise PermissionError(msg)

    accreditation = get_accreditation(event, user)
    if accreditation is not None:
        if accreditation.status in _BLOCKS_A_NEW_REQUEST:
            return accreditation
        # WITHDRAWN : le membre revient sur sa décision.
        accreditation.status = AccreditationStatus.REQUESTED
        accreditation.requested_at = arrow.utcnow()
        accreditation.decided_at = None
        accreditation.decided_by_id = None
        notify_request_received(event, user)
        return accreditation

    accreditation = Accreditation(
        event_id=event.id,
        user_id=user.id,
        status=AccreditationStatus.REQUESTED,
    )
    db.session.add(accreditation)
    notify_request_received(event, user)
    return accreditation


def withdraw_accreditation(event: EventPost, user: User) -> Accreditation | None:
    """Annuler sa demande, ou se désinscrire (RG-08).

    Les deux gestes sont le même côté membre. Renvoie `None` si le
    membre n'avait rien demandé — un retrait sans demande est un no-op,
    pas une erreur (RG-10).

    Raises:
        AccreditationClosedError: l'événement a été annulé (ANN-05).
    """
    if event.cancelled_at is not None:
        # ANN-05 — sur un événement annulé, plus aucun geste
        # d'engagement. Les lignes existantes sont conservées (RG-12) :
        # ce sont elles qui disent à qui l'on doit un message si
        # l'événement est rétabli.
        msg = "Cet événement a été annulé."
        raise AccreditationClosedError(msg)

    accreditation = get_accreditation(event, user)
    if accreditation is None:
        return None

    if accreditation.status == AccreditationStatus.REJECTED:
        # Un refus est définitif côté membre (D5). Sans cette garde, il
        # suffirait de « se retirer » d'un refus pour repasser en
        # WITHDRAWN — que RG-03 laisse re-demander — et le harcèlement
        # par re-demandes que la règle interdit redeviendrait possible.
        return accreditation

    accreditation.status = AccreditationStatus.WITHDRAWN
    notify_withdrawn(event, user)
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

    # Les seuls états d'où une décision peut partir. Sans ce filtre, un
    # POST forgé ferait passer un WITHDRAWN en ACCEPTED — une arête que
    # la machine à états n'a pas : seul le membre sort de WITHDRAWN.
    sources = _DECIDABLE_FROM[status]

    # Relevé **avant** l'UPDATE : on ne notifie que les lignes
    # réellement touchées. Notifier `user_ids` tel quel enverrait cloche
    # et email à n'importe quel identifiant posté dans le formulaire, y
    # compris à des membres qui n'ont jamais rien demandé.
    touched = list(
        db.session.scalars(
            sa.select(Accreditation.user_id).where(
                Accreditation.event_id == event.id,
                Accreditation.user_id.in_(user_ids),
                Accreditation.status.in_(sources),
            )
        )
    )
    if not touched:
        return 0

    stmt = (
        sa.update(Accreditation)
        .where(
            Accreditation.event_id == event.id,
            Accreditation.user_id.in_(touched),
        )
        .values(
            status=status,
            decided_at=arrow.utcnow(),
            decided_by_id=decided_by.id,
        )
    )
    result = db.session.execute(stmt, execution_options={"synchronize_session": False})
    db.session.expire_all()

    # NOT-02 / NOT-03 — une notification par destinataire réellement
    # touché. La décision est un fait pour chacun d'eux séparément ;
    # l'UPDATE groupé est une optimisation de stockage, pas un message
    # collectif.
    notify = (
        notify_accepted if status == AccreditationStatus.ACCEPTED else notify_rejected
    )
    for member in db.session.scalars(sa.select(User).where(User.id.in_(touched))):
        notify(event, member)

    return result.rowcount


def is_open(event: EventPost) -> bool:
    """L'événement accepte-t-il encore un geste d'engagement ?

    Le **même** prédicat masque les boutons et refuse le POST. Les deux
    expressions séparées d'hier — une garde dans le service, une copie
    dans la vue — ne pouvaient que diverger : masquer sans refuser
    laisse passer un POST forgé, refuser sans masquer affiche un bouton
    mort.
    """
    return not _closed_reason(event)


def _closed_reason(event: EventPost) -> str:
    """Ce qui ferme l'événement, en clair, ou une chaîne vide.

    Trois motifs, dans l'ordre où ils comptent : pas publié, annulé
    (ANN-05), commencé (RG-04).
    """
    if event.status != PublicationStatus.PUBLIC:
        return "Cet événement n'est pas publié."
    if event.cancelled_at is not None:
        return "Cet événement a été annulé."
    if event.start_datetime is not None and event.start_datetime <= arrow.utcnow():
        return "Cet événement a commencé ; les demandes sont closes."
    return ""


def _require_open(event: EventPost) -> None:
    reason = _closed_reason(event)
    if reason:
        raise AccreditationClosedError(reason)


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
    """Le membre peut-il demander une accréditation à cet événement ?

    RG-05 — la restriction au rôle `PRESS_MEDIA` sur **tous** les
    événements est levée. C'était l'écart E1 : le livré interdisait à
    un universitaire de s'inscrire à un webinaire académique, et aucune
    spécification ne le demandait. Le seul filtre est désormais le
    ciblage choisi par l'organisateur ; un événement de presse se
    restreint aux journalistes en cochant leur communauté, pas par une
    règle codée en dur.
    """
    return in_audience(user, event.audience or [])
