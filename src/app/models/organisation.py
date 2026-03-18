# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""
'-----------------------------------------------------------------
'Corporate pages / info
'-----------------------------------------------------------------
"""

from __future__ import annotations

import arrow
import sqlalchemy as sa
from slugify import slugify
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy_utils import ArrowType

from app.enums import BWTypeEnum, OrganisationTypeEnum
from app.models.auth import User
from app.models.base import Base
from app.models.mixins import Addressable, IdMixin, LifeCycleMixin


class Organisation(IdMixin, LifeCycleMixin, Addressable, Base):
    """
    Remarques:
        - pas de SIRET

        Ajouts:
            - tva
    """

    __tablename__ = "crp_organisation"

    name: Mapped[str]  # nom officiel de l'organisation  # all
    slug: Mapped[str]  # internal

    # from LifeCycleMixin : created_at
    # from LifeCycleMixin : deleted_at

    modified_at: Mapped[arrow.Arrow | None] = mapped_column(
        ArrowType(timezone=True), nullable=True, onupdate=arrow.utcnow
    )

    # keep only organisation.type?
    # -> mandatory for the organisation edit page
    bw_type: Mapped[BWTypeEnum] = mapped_column(
        sa.Enum(BWTypeEnum),
        nullable=True,
    )

    # active flag : by default organisations are active, they can be
    # deactivated by site admin or when they lose their BW registration
    # In that case they become like "AUTO" orgs as regards display of pages
    active: Mapped[bool] = mapped_column(default=True)

    status: Mapped[str] = mapped_column(default="")
    karma: Mapped[int] = mapped_column(default=0)

    members = relationship(
        User,
        primaryjoin="User.organisation_id == Organisation.id",
        back_populates="organisation",
    )

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        if "slug" not in kwargs:
            self.slug = slugify(self.name)

    def __repr__(self) -> str:
        return f"<Organisation {self.name}>"

    @property
    def is_auto(self) -> bool:
        """To be fixed later (make it a bool attribute or remove)

        Always returns False.
        Organisations are now considered 'auto' only if they have no active BW.
        """
        return not self.active

    @property
    def is_auto_or_inactive(self) -> bool:
        """Returns True if organisation is inactive (no active BW)."""
        return not self.active


__1 = """

- Téléverser le logo de l’organisation.
- Téléverser une image de fonds de bandeau
- Saisissez les informations :
- nom et typo officiels de l’organisation
- adresse du siège social, code postal, ville, pays
- n° Siret, Siren, TVA intracommunautaire
- nom et coordonnées du dirigeant

- Inscrivez vos délégataires et attribuez-leur des droits
    1- inscriptions collectives : créer, éditer, valider, modifier, supprimer les profils
    2- communiqués de presse : créer, éditer, valider, modifier, supprimer
    3- événements (événements de presse, événements publics, événements culturels, formations, concours) : créer, éditer, valider, modifier, supprimer
    4- justificatifs de publication : éditer, valider, modifier, supprimer
    5- mission : créer, éditer, valider, modifier, supprimer
    6- appels d’offre : créer, éditer, valider, modifier, supprimer
    7- offres d’emploi : créer, éditer, valider, modifier, supprimer
    8- publication des offres de stage : créer, éditer, valider, modifier, supprimer
    9- partenariats
    9-1 mutualiser le financement d’enquêtes, reportages ou dossiers avec des médias complémentaires
    9-2 mutualiser des moyens techniques ou des compétences avec des médias complémentaires
    pour un projet éditorial
    pour un projet de communication
    pour un projet d’événement

    9-3 pour mener un projet d’innovation digitale
    pour recruter un ingénieur assistant à la maîtrise d’ouvrage (rédiger le cag-hier des charges, lancer l’appel d’offre, dépouiller les résultats et suivre le projet)
    pour lancer un appel d’offre

    10- abondement du porte-monnaie électronique Corporate : créer, éditer, valider, modifier, supprimer
    11- attribution des portes-monnaies électroniques auprès des collaborateurs bénéficiaires : créer, éditer, valider, modifier, supprimer

→  Faire le tableau de l’attribution des rôles, des tâches, des achats, des ventes
"""

__2 = """
### Page agence de presse

NB: Lors de la réunion du 02 sept., on avait conclut qu'on ne pouvait pas tout faire. On va se contenter de ce qui peut être automatisé.

Texte de présentation
Les collaborateurs

Références clients
URL du site à ouvrir dans un autre onglet
Dernières actualités
Dernières News  Contacts
Demande d’information commerciale
Demande de partenariat
Demande de stage
Proposer un sujet

### Pages média

Texte de présentation
Les collaborateurs
Calendrier rédactionnel (ajouter un bouton réservez votre espace publicitaire)
URL du site à ouvrir dans un autre onglet
Dernières actualités
Dernières News
Contacts :
Demande d’information commerciale
Souscrire à un abonnement
Demande de partenariat
Demande de stage
Proposer un sujet
Réservez votre espace
Consultez nos tarifs (espace 1, espace 2, etc.)

### Page association de journalistes

Texte de présentation
Le conseil d’administration
Les membres de l’association
Les médias représentés
Les partenaires
Bouton URL du site à ouvrir dans un autre onglet
Bouton : parrainez des membres
Dernières actualités
Derniers membres inscrits
Calendrier des événements
Boutons :
demande d’inscription à l’association
demande de partenariat
demande de stage

### Page clubs de la presse

Texte de présentation
Le conseil d’administration
Les membres de l’association
Les médias représentés
les cabinets de relation presse représentés
Les sponsors
Les partenaires
Bouton URL du site à ouvrir dans un autre onglet
Bouton : parrainez des membres
Dernières actualités
Derniers membres inscrits
Calendrier des événements
Boutons :
demande d’inscription à l’association
demande de partenariat
demande de stage

"""
