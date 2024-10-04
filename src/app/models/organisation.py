# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""
'-----------------------------------------------------------------
'Corporate pages / info
'-----------------------------------------------------------------

abstract class OrganisationPage {
    +website_url URL
    +linkedin_url URL
    +siren_number SIREN
    +mission HTML
    +baseline string
    +logo Image
}
OrganisationPage -up-|> BaseContent

class MediaCompanyPage {
    +NoAgreement: string
    TODO contenu à définir
}
note bottom: Avec un numéro d agrément ou un numéro de Commission Paritaire

MediaCompanyPage -up-|> OrganisationPage

class CommunicationCompanyPage {
    TODO contenu à définir
}
CommunicationCompanyPage -up-|> OrganisationPage

class OtherOrganisationPage {
    TODO contenu à définir
}
OtherOrganisationPage -up-|> OrganisationPage
"""

from __future__ import annotations

import sqlalchemy as sa
from slugify import slugify
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.enums import OrganisationFamilyEnum
from app.models.auth import User
from app.models.base import Base
from app.models.geoloc import GeoLocation
from app.models.mixins import Addressable, IdMixin, LifeCycleMixin, Owned


class Organisation(IdMixin, LifeCycleMixin, Owned, Addressable, Base):
    """
    -ID: int[1] {id. readOnly. unique}
    -Nom: String[I]
    -Logo: Logo[0..I]
    -Pays: String[1..+] {ordered}
    -Téléphones: NumeroDeTelephone[0..1] {ordered. unique}
    -Dirigeants: Collaborateur[1..1 {ordered}
    -Collaborateurs: Collaborateur[0.1 {ordered}
    -Départements: Département[0.1 {ordered}
    -Filiales: Filiale[0..1] {ordered}
    -BusinessUnits: BusinessUnit[0.1 {ordered}
    -Agences: Age.nces[0..A] {ordered}

    -PorteMonnaie: PorteMonnaieElectronique[0..1]

    -ContactsPresse: ContactRelationPresse[0.1 {ordered}

    -Actualités: Actualité[0.1 {ordered}

    -Événements: Événeme.nt[0.1 {ordered}
    -Attented: Événement[0.1 {ordered}

    -GalleriePropriétaire: Image[0 {ordered}
    -GalleriePartagée: Image[0.1 {ordered}
    -Effectifs: int[1] = 0
    -CotéEnBourse: Boolean[I]
    -MarchésBoursiers: MarchéBoursier[0..A] {ordered}

    -Réputation: Réputation[I]

    -Demandes: Demande[0..n] {ordered}
    -DemandessPassées: Dernande[0..n] {ordered}
    -Offres: Offre[0..n] {ordered}
    -OffresPassées: Offre[0..n] {ordered}
    """

    __tablename__ = "crp_organisation"

    name: Mapped[str]
    slug: Mapped[str]
    siren: Mapped[str] = mapped_column(default="")

    description: Mapped[str] = mapped_column(default="")
    metiers: Mapped[str] = mapped_column(default="")

    # name = sa.Column(sa.UnicodeText, nullable=False)
    # slug = sa.Column(sa.UnicodeText, nullable=False)
    # siren = sa.Column(sa.UnicodeText, default="")
    # description = sa.Column(sa.UnicodeText, default="")

    geoloc_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("geo_loc.id"), nullable=True
    )
    geoloc: Mapped[GeoLocation] = relationship(GeoLocation)

    # geoloc_id = sa.Column(sa.Integer, sa.ForeignKey("geo_loc.id"), nullable=True)
    # geoloc = sa.orm.relationship(GeoLocation)
    #
    type: Mapped[OrganisationFamilyEnum] = mapped_column(
        sa.Enum(OrganisationFamilyEnum), default=OrganisationFamilyEnum.AUTRE, index=True
    )

    karma: Mapped[int] = mapped_column(default=0)

    # Web presence
    domain: Mapped[str] = mapped_column(default="")
    site_url: Mapped[str] = mapped_column(default="")
    jobs_url: Mapped[str] = mapped_column(default="")
    github_url: Mapped[str] = mapped_column(default="")
    linkedin_url: Mapped[str] = mapped_column(default="")

    # Pictures
    logo_url: Mapped[str] = mapped_column(default="")
    cover_image_url: Mapped[str] = mapped_column(default="")

    logo_id: Mapped[str] = mapped_column(default="")
    cover_image_id: Mapped[str] = mapped_column(default="")
    screenshot_id: Mapped[str] = mapped_column(default="")

    members = relationship(
        User,
        primaryjoin="User.organisation_id == Organisation.id",
        back_populates="organisation",
    )

    # no_siret = sa.Column(sa.UnicodeText, default="")
    # no_siren = sa.Column(sa.UnicodeText, default="")
    # no_tva = sa.Column(sa.UnicodeText, default="")

    # Specifique aux agences de presse
    agree_cppap: Mapped[bool] = mapped_column(default=False)
    membre_sapi: Mapped[bool] = mapped_column(default=False)
    membre_satev: Mapped[bool] = mapped_column(default=False)
    membre_saphir: Mapped[bool] = mapped_column(default=False)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        if "slug" not in kwargs:
            self.slug = slugify(self.name)


# class OrgFullProfile(Base):
#     __tablename__ = "crp_org_full_profile"
#
#     id = sa.Column(sa.Integer, sa.ForeignKey("crp_organisation.id"), primary_key=True)
#     organisation = sa.orm.relationship(Organisation, back_populates="full_profile")
#
#     presentation = sa.Column(sa.UnicodeText, default="")
#
#     no_siret = sa.Column(sa.UnicodeText, default="")
#     no_siren = sa.Column(sa.UnicodeText, default="")
#     no_tva = sa.Column(sa.UnicodeText, default="")


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

# class Employer(IdMixin, LifeCycleMixin, Owned, Base):
#     __tablename__ = "job_employer"
#
#     name = sa.Column(sa.UnicodeText, nullable=False)
#     slug = sa.Column(sa.UnicodeText, nullable=False)
#     siren = sa.Column(sa.UnicodeText, default="")
#     description = sa.Column(sa.UnicodeText, default="")
#     #
#     status = sa.Column(sa.UnicodeText, default=STATUS.PENDING, index=True)
#     karma = sa.Column(sa.Integer, default=0)
#     #
#     domain = sa.Column(sa.UnicodeText, default="")
#     site_url = sa.Column(sa.UnicodeText, default="")
#     jobs_url = sa.Column(sa.UnicodeText, default="")
#     github_url = sa.Column(sa.UnicodeText, default="")
#     linkedin_url = sa.Column(sa.UnicodeText, default="")
#     # Backrefs
#     job_posts = sa.orm.relationship("JobPost", back_populates="employer")
#
#     def __init__(self, **kwargs):
#         super().__init__(**kwargs)
#         if "slug" not in kwargs:
#             self.slug = slugify(self.name)
