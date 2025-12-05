# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""
'-----------------------------------------------------------------
'Corporate pages / info
'-----------------------------------------------------------------
"""

from __future__ import annotations

from datetime import UTC, datetime

import arrow
import sqlalchemy as sa
from advanced_alchemy.types.file_object import FileObject, StoredObject
from slugify import slugify
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy_utils import ArrowType
from sqlalchemy_utils.functions.orm import hybrid_property

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

    # note: adding unique=True to siren and TVA breaks session.merge(), this would
    # require a composite key, thus requiring to provide siren and tva on all requests
    # involding the id of the organisation
    siren: Mapped[str] = mapped_column(nullable=True)  # all
    tva: Mapped[str] = mapped_column(nullable=True)  # all

    # nom officiel du titre (média, agence presse) pour les media ou aggency,
    # ou administration. Ou nom de micro entreprise (label different dans forms)
    # BW: media, micro, corporate, pressunion
    nom_groupe: Mapped[str] = mapped_column(default="")

    # OBSOLETE
    tel_standard: Mapped[str] = mapped_column(default="")

    # ONTOLOGIES/Tailles des organisations
    # all
    taille_orga: Mapped[str] = mapped_column(default="")  # cf ontologies

    # Nom et coordonnées directes du dirigeant
    # Préférer "Contact officiel" ?
    # -> champ descriptif
    # all
    leader_name: Mapped[str] = mapped_column(default="")
    leader_coords: Mapped[str] = mapped_column(default="")

    # Nom et coordonnées directes du payeur
    # -> champ descriptif
    payer_name: Mapped[str] = mapped_column(default="")
    payer_coords: Mapped[str] = mapped_column(default="")

    #  Adresse du siège social ;
    #  Code postal ;
    # Géolocalisation : macro-région, pays, région, département, ville (ONTOLOGIES/Géolocalisation) ;

    # secteurs d’activité : ONTOLOGIES/Secteur détaillés
    # métiers : ONTOLOGIES/Domaines & Métiers ;
    # nombre de salariés  : ONTOLOGIES/Tailles des Organisations ;
    # nombre de salariés  : ONTOLOGIES/Tailles des Organisations ;

    # Principaux événements organisés

    # question :
    # le type d'organisation (cf ONTOLOGIES/Types d'organisation)
    # -> ce n'est pas pour les medias/agencies...'
    # le secteur d’activité (cf ONTOLOGIES/Secteurs détaillés) ;
    # -> uniquement pour presse / media ?
    #  + question unicité...

    # OBSOLETE
    description: Mapped[str] = mapped_column(default="")

    # OBSOLETE
    metiers: Mapped[dict] = mapped_column(JSON, default=list)
    # OBSOLETE
    metiers_detail: Mapped[dict] = mapped_column(JSON, default=list)

    # from LifeCycleMixin : created_at
    # from LifeCycleMixin : deleted_at

    modified_at: Mapped[arrow.Arrow | None] = mapped_column(
        ArrowType(timezone=True), nullable=True, onupdate=arrow.utcnow
    )

    # geoloc_id = sa.Column(sa.Integer, sa.ForeignKey("geo_loc.id"), nullable=True)
    # geoloc = sa.orm.relationship(GeoLocation)
    #
    type: Mapped[OrganisationTypeEnum] = mapped_column(
        sa.Enum(OrganisationTypeEnum),
        default=OrganisationTypeEnum.AUTO,
        index=True,
    )

    # keep only organisation.type?
    # -> mandatory for the organisation edit page
    bw_type: Mapped[BWTypeEnum] = mapped_column(
        sa.Enum(BWTypeEnum),
        nullable=True,
    )

    creator_profile_code: Mapped[str] = mapped_column(default="")

    # active flag : by default organisations are active, they can be
    # deactivated by site admin or when they lose their BW registration
    # In that case they become like "AUTO" orgs as regards display of pages
    active: Mapped[bool] = mapped_column(default=True)
    stripe_subscription_status: Mapped[str] = mapped_column(nullable=True)
    stripe_product_id: Mapped[str] = mapped_column(default="")
    stripe_product_quantity: Mapped[int] = mapped_column(default=0)
    stripe_subscription_id: Mapped[str] = mapped_column(default="")
    stripe_latest_invoice_url: Mapped[str] = mapped_column(default="")
    stripe_subs_creation_date: Mapped[datetime] = mapped_column(
        ArrowType(timezone=True), default=datetime(2000, 1, 1, tzinfo=UTC)
    )
    # stripe_subs_current_period_end: Mapped[datetime] = mapped_column(
    #     ArrowType, default=datetime(2000, 1, 1, tzinfo=timezone.utc)
    # )
    stripe_subs_current_period_start: Mapped[datetime] = mapped_column(
        ArrowType(timezone=True), default=datetime(2000, 1, 1, tzinfo=UTC)
    )
    validity_date: Mapped[datetime] = mapped_column(
        ArrowType(timezone=True), default=datetime(2000, 1, 1, tzinfo=UTC)
    )

    status: Mapped[str] = mapped_column(default="")
    karma: Mapped[int] = mapped_column(default=0)

    # Web presence
    site_url: Mapped[str] = mapped_column(default="")

    # NOUVEAU
    # galerie d'images

    logo_image: Mapped[FileObject | None] = mapped_column(
        StoredObject(backend="s3"), nullable=True
    )
    cover_image: Mapped[FileObject | None] = mapped_column(
        StoredObject(backend="s3"), nullable=True
    )
    screenshot_id: Mapped[str] = mapped_column(default="")

    members = relationship(
        User,
        primaryjoin="User.organisation_id == Organisation.id",
        back_populates="organisation",
    )

    # no_siret = sa.Column(sa.UnicodeText, default="")
    # no_siren = sa.Column(sa.UnicodeText, default="")
    # no_tva = sa.Column(sa.UnicodeText, default="")

    # NOUVEAU
    # adresse postale du siège
    pays_zip_ville: Mapped[str] = mapped_column(default="")  # all
    pays_zip_ville_detail: Mapped[str] = mapped_column(default="")  # all

    # Specifique aux agences de presse
    agree_arcom: Mapped[bool] = mapped_column(default=False)
    agree_cppap: Mapped[bool] = mapped_column(default=False)
    number_cppap: Mapped[str] = mapped_column(default="")
    membre_saphir: Mapped[bool] = mapped_column(default=False)
    membre_sapi: Mapped[bool] = mapped_column(default=False)
    membre_satev: Mapped[bool] = mapped_column(default=False)

    # discussion: 3 types de secteurs d'activité
    # media, micro, corporate, presunion, com
    secteurs_activite_medias: Mapped[dict] = mapped_column(JSON, default=list)
    secteurs_activite_medias_detail: Mapped[dict] = mapped_column(JSON, default=list)
    secteurs_activite_rp: Mapped[dict] = mapped_column(JSON, default=list)
    secteurs_activite_rp_detail: Mapped[dict] = mapped_column(JSON, default=list)
    secteurs_activite: Mapped[dict] = mapped_column(JSON, default=list)
    secteurs_activite_detail: Mapped[dict] = mapped_column(JSON, default=list)

    # OBSOLETE
    transformation_majeure: Mapped[dict] = mapped_column(JSON, default=list)
    transformation_majeure_detail: Mapped[dict] = mapped_column(JSON, default=list)

    # ONTOLOGIES/Types d’organisation :
    type_organisation: Mapped[dict] = mapped_column(JSON, default=list)  # all
    type_organisation_detail: Mapped[dict] = mapped_column(JSON, default=list)  # all

    # ONTOLOGIES/Types d’entreprise de presse et média
    # média, micro, corporate, pressunion
    type_entreprise_media: Mapped[dict] = mapped_column(JSON, default=list)

    # ONTOLOGIES/Types de presse et média
    # média, micro, corporate
    type_presse_et_media: Mapped[dict] = mapped_column(JSON, default=list)

    # ONTOLOGIES/Types PR Agency
    # com
    type_agence_rp: Mapped[dict] = mapped_column(JSON, default=list)

    # NOUVEAU
    # en discussion: clients connus de aipress24
    # clients: Mapped[str] = mapped_column(default="")

    # OBSOLETE
    main_events: Mapped[str] = mapped_column(default="")  #
    number_customers: Mapped[int] = mapped_column(default=0)  #
    main_customers: Mapped[str] = mapped_column(default="")  #
    main_prizes: Mapped[str] = mapped_column(default="")  #

    # média, micro, corporate.  300 signes
    positionnement_editorial: Mapped[str] = mapped_column(default="")

    # média, micro, corporate.  500 signes
    audience_cible: Mapped[str] = mapped_column(default="")

    # OBSOLETE
    tirage: Mapped[str] = mapped_column(default="")  #

    # ONTOLOGIES/Périodicité
    # media, corporate
    frequence_publication: Mapped[str] = mapped_column(default="")

    # OBSOLETE
    metiers_presse: Mapped[dict] = mapped_column(JSON, default=list)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        if "slug" not in kwargs:
            self.slug = slugify(self.name)

    def __repr__(self) -> str:
        return f"<Organisation {self.name}>"

    @property
    def is_auto(self) -> bool:
        return self.type == OrganisationTypeEnum.AUTO

    @property
    def is_bw_active(self) -> bool:
        return self.type != OrganisationTypeEnum.AUTO and self.active

    @property
    def is_bw_valid_date(self) -> bool:
        """Return True if the BW validity date is in the future."""
        return (
            self.type != OrganisationTypeEnum.AUTO
            and self.active
            and self.validity_date.date() >= datetime.now(tz=UTC).date()
        )

    @property
    def is_bw_inactive(self) -> bool:
        return self.type != OrganisationTypeEnum.AUTO and not self.active

    @property
    def is_auto_or_inactive(self) -> bool:
        return self.type == OrganisationTypeEnum.AUTO or not self.active

    @property
    def is_agency(self) -> bool:
        return self.type == OrganisationTypeEnum.AGENCY

    @hybrid_property
    def managers(self) -> list[User]:
        return [user for user in self.members if user.is_manager]

    @hybrid_property
    def leaders(self) -> list[User]:
        return [user for user in self.members if user.is_leader]

    def cover_image_signed_url(self, expires_in: int = 3600) -> str:
        file_obj: FileObject | None = self.cover_image
        if file_obj is None:
            return "/static/img/transparent-square.png"
        try:
            return file_obj.sign(expires_in=expires_in, for_upload=False)
        except RuntimeError as e:
            msg = f"Storage failed to sign URL for cover image org.id : {self.id}, key {file_obj.object_key}: {e}"
            raise RuntimeError(msg) from e

    def logo_image_signed_url(self, expires_in: int = 3600) -> str:
        file_obj: FileObject | None = self.logo_image
        if file_obj is None:
            return "/static/img/transparent-square.png"
        try:
            return file_obj.sign(expires_in=expires_in, for_upload=False)
        except RuntimeError as e:
            msg = f"Storage failed to sign URL for logo image org.id : {self.id}, key {file_obj.object_key}: {e}"
            raise RuntimeError(msg) from e


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
