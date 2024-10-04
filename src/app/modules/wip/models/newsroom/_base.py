# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import orm
from sqlalchemy.orm import Mapped, mapped_column

from app.models.auth import User
from app.models.mixins import IdMixin, LifeCycleMixin, Owned
from app.models.organisation import Organisation


class NewsroomCommonMixin(IdMixin, LifeCycleMixin, Owned):
    # Auteur
    # -> owner_id

    # Media
    media_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey(Organisation.id))

    # Commanditaire
    commanditaire_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey(User.id))

    # Titre
    titre: Mapped[str] = mapped_column(default="")

    # Titre
    brief: Mapped[str] = mapped_column(default="")

    # N° d’édition
    numero_edition: Mapped[str] = mapped_column(default="")

    # Contenu
    contenu: Mapped[str] = mapped_column(default="")

    # Type
    type_contenu: Mapped[str] = mapped_column(default="")

    # Taille
    taille_contenu: Mapped[str] = mapped_column(default="")

    @orm.declared_attr
    def media(cls):
        return orm.relationship(Organisation, foreign_keys=[cls.media_id])

    # Temp hack
    @property
    def title(self):
        return self.titre

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.id}>"


class NewsMetadataMixin:
    # NEWS-Genres
    genre: Mapped[str] = mapped_column(default="")

    # NEWS-Rubriques
    section: Mapped[str] = mapped_column(default="")

    # NEWS-Types d’info / "Thémtique"
    topic: Mapped[str] = mapped_column(default="")

    # NEWS-Secteurs
    sector: Mapped[str] = mapped_column(default="")

    # Géo-localisation
    geo_localisation: Mapped[str] = mapped_column(default="")

    # Langue
    language: Mapped[str] = mapped_column(default="fr")


class CiblageMixin:
    # Secteurs détaillés
    ciblage_secteur_detailles: Mapped[str] = mapped_column(default="")

    # Directions & Expertise
    ciblage_directions_expertise: Mapped[str | None] = mapped_column(default="")

    # Types d’organisation
    ciblage_types_organisation: Mapped[str | None] = mapped_column(default="")

    # Tailles d’organisation
    ciblage_tailles_organisation: Mapped[str | None] = mapped_column(default="")

    # Géo-localisation (doublon?)
    ciblage_geolocation: Mapped[str | None] = mapped_column(default="")


class StatutMixin:
    statut: Mapped[str] = mapped_column(default="")


#
# class Ignore:
#     # Liste du 04/12/2023
#     # (Correspondance des attributs entre les étapes du processus de newsroom)
#
#     # Media
#     media_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("media.id"))
#
#     # Commanditaire
#     commanditaire_id: Mapped[int] = mapped_column(
#         sa.BigInteger, sa.ForeignKey("media.id")
#     )
#
#     # Auteur
#     # -> owner_id
#
#     # Titre
#     # -> title
#
#     # N° d’édition
#     numero_edition: Mapped[str] = mapped_column(default="")
#
#     # Contenu
#     # -> content
#
#     # NEWS-Secteurs
#     secteurs: Mapped[str] = mapped_column(default="")
#
#     # NEWS-Rubriques
#     rubrique: Mapped[str] = mapped_column(default="")
#
#     # NEWS-Types d’info
#     type_info: Mapped[str] = mapped_column(default="")
#
#     # NEWS-Genres
#     genre: Mapped[str] = mapped_column(default="")
#
#     # Géo-localisation
#     geo_localisation: Mapped[str] = mapped_column(default="")
#
#     # Langue
#     langue: Mapped[str] = mapped_column(default="fr")
#
#     # ------------------------------------------------------------
#     # Statut
#     # ------------------------------------------------------------
#
#     # OUI: Public NON: Ciblé
#     visibilite: Mapped[str] = mapped_column(default="")
#
#     # Etat: Accepté, Refusé, En discussion, Annulé
#     etat_validation: Mapped[str] = mapped_column(default="")
#
#     # Etat: Brouillon, Validé, Publié
#     etat_publication: Mapped[str] = mapped_column(default="")
#
#     # ------------------------------------------------------------
#     # Dates
#     # ------------------------------------------------------------
#
#     # Limite de validité
#     date_limite_validite: Mapped[datetime] = mapped_column(sa.DateTime)
#
#     # Fin de l’enquête
#     date_fin_enquete: Mapped[datetime] = mapped_column(sa.DateTime)
#
#     # Bouclage
#     date_bouclage: Mapped[datetime] = mapped_column(sa.DateTime)
#
#     # Parution prévue
#     date_parution_prevue: Mapped[datetime] = mapped_column(sa.DateTime)
#
#     # Publié sur AIP24
#     date_publication_aip24: Mapped[datetime] = mapped_column(sa.DateTime)
#
#     # Paiement
#     date_paiement: Mapped[datetime] = mapped_column(sa.DateTime)
#
#     # ------------------------------------------------------------
#     # Ciblage
#     # ------------------------------------------------------------
#
#     # Secteurs détaillés
#     secteur_detailles: Mapped[str] = mapped_column(default="")
#
#     # Directions & Expertise
#     directions_expertise: Mapped[str] = mapped_column(default="")
#
#     # Types d’organisation
#     types_organisation: Mapped[str] = mapped_column(default="")
#
#     # Tailles d’organisation
#     tailles_organisation: Mapped[str] = mapped_column(default="")
#
#     # Géo-localisation (doublon?)
#
#     # ------------------------------------------------------------
#     # Contenu éditorial
#     #
#
#     # Type
#     type_contenu: Mapped[str] = mapped_column(default="")
#
#     # Taille
#     taille_contenu: Mapped[str] = mapped_column(default="")
#
#     # ------------------------------------------------------------
#     # Achat de contenus éditoriaux
#     # ------------------------------------------------------------
#
#     # Modes de paiement
#     mode_paiement: Mapped[str] = mapped_column(default="")
#
#     # Tarif
#     tarif: Mapped[str] = mapped_column(default="")
#
#     # ------------------------------------------------------------
#     # Approbation pour vente
#     # ------------------------------------------------------------
#
#     # Consultation
#     consultation: Mapped[str] = mapped_column(default="")
#
#     # Justificatif de publication
#     justificatif_publication: Mapped[str] = mapped_column(default="")
#
#     # Cession de droits d’auteur
#     cession_droits_auteur: Mapped[str] = mapped_column(default="")
