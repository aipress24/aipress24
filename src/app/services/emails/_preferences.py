# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""La préférence du destinataire, lue au moment d'envoyer — `PRF-03`.

Le point d'envoi ne connaît qu'une **adresse**, pas un membre : c'est
la même contrainte que le contrôle de quota juste à côté, et la même
réponse — une recherche par adresse.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import scoped_session
from svcs.flask import container

from app.enums import NotificationCategory


def recipient_wants(recipient: str, category: NotificationCategory) -> bool:
    """Ce destinataire accepte-t-il les emails de cette famille ?

    Trois situations rendent « oui », et aucune n'est une garde
    défensive — ce sont trois façons de n'avoir jamais rien refusé
    (`PRF-04`) :

    - le message est **transactionnel**, donc jamais désactivable : on
      ne refuse pas la réponse à sa propre demande ;
    - aucun compte ne porte cette adresse — invitation d'un tiers,
      partage vers l'extérieur ;
    - le compte n'a pas de profil, ou son profil n'a rien coupé.
    """
    if category == NotificationCategory.TRANSACTIONAL:
        return True

    profile = _profile_of(recipient)
    if profile is None:
        return True
    return profile.wants_notification(category)


def _profile_of(recipient: str):
    """Le profil du membre qui porte cette adresse, s'il y en a un.

    Une requête par envoi, comme le contrôle de quota voisin, et pour
    la même raison : le point d'envoi ne reçoit qu'une chaîne.
    """
    from app.models.auth import KYCProfile, User

    db_session = container.get(scoped_session)
    stmt = (
        sa.select(KYCProfile)
        .join(User, User.id == KYCProfile.user_id)
        .where(sa.func.lower(User.email) == recipient.lower().strip())
    )
    return db_session.scalars(stmt).first()
