# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Affichage du tarif d'un événement — `PRX-04`.

Le libellé dépend du **lecteur** : un journaliste et un autre membre ne
voient pas la même chose d'un événement gratuit pour la presse. C'est
la seule information d'une carte d'événement dans ce cas, et elle vit
donc ici plutôt que dans un gabarit — une condition à trois branches et
deux publics se relit mieux comme une fonction que comme un `{% if %}`
imbriqué, et se teste sur ses six combinaisons.

Rien n'est encaissé (`PRX-05`) : le prix est une information
éditoriale, le paiement se fait auprès de l'organisateur.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.enums import EventPricing, RoleEnum
from app.modules.events.services import is_signed_in
from app.ui.money import format_cents

if TYPE_CHECKING:
    from app.models.auth import User


def price_label(event, user: User | None) -> str:
    """Le tarif de l'événement, tel que ce lecteur doit le lire.

    Les six combinaisons du tableau `PRX-04` :

    ============================  ===================  ==========================
    `pricing`                     journaliste          autre membre
    ============================  ===================  ==========================
    `FREE_FOR_ALL`                Gratuit              Gratuit
    `FREE_FOR_JOURNALISTS`        Gratuit pour les…    45,00 € — gratuit pour les…
    `PAID`                        45,00 €              45,00 €
    ============================  ===================  ==========================

    Un visiteur anonyme lit la colonne « autre membre » : c'est le
    montant qu'il paierait, et lui montrer « gratuit » serait un
    mensonge sur lequel il se déplacerait.
    """
    pricing = event.pricing
    if pricing == EventPricing.FREE_FOR_ALL:
        return "Gratuit"

    amount = format_cents(event.price, event.currency)
    if pricing == EventPricing.PAID:
        return amount
    if pricing == EventPricing.FREE_FOR_JOURNALISTS:
        if is_journalist(user):
            return "Gratuit pour les journalistes"
        return f"{amount} — gratuit pour les journalistes"

    # Trois branches explicites, pas de fourre-tout : un `pricing`
    # inattendu — `None` sur un objet jamais enregistré, une valeur
    # ajoutée à l'énumération sans passer par ici — tombait dans la
    # branche « gratuit pour les journalistes » et annonçait un tarif
    # faux plutôt que d'échouer.
    msg = f"Modalité tarifaire inconnue : {pricing!r}"
    raise ValueError(msg)


def is_journalist(user: User | None) -> bool:
    """Le lecteur appartient-il à la communauté de la presse ?

    `has_role` et non `first_community()` : celle-ci lève
    `RuntimeError` pour un utilisateur sans rôle de communauté — un
    administrateur, un compte de service — et renvoie de toute façon un
    `RoleEnum` là où l'on attendrait un `CommunityEnum`.
    """
    if not is_signed_in(user):
        return False
    return user.has_role(RoleEnum.PRESS_MEDIA)
