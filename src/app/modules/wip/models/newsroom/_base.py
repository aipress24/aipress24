# Copyright (c) 2021-2024, Abilian SAS & TCA
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

    # Brief
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
        return orm.relationship(Organisation, foreign_keys=[cls.media_id])  # type: ignore[arg-type]

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
