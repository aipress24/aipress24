# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from aenum import StrEnum, auto
from sqlalchemy import BigInteger, Enum, ForeignKey, String, orm
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy_utils import ArrowType

from app.models.base_content import BaseContent
from app.models.mixins import IdMixin, LifeCycleMixin, Owned
from app.models.organisation import Organisation
from app.services.tagging.interfaces import Taggable


class PostStatus(StrEnum):
    DRAFT = auto()
    PUBLIC = auto()
    ARCHIVED = auto()


DRAFT = PostStatus.DRAFT


class PublisherType(StrEnum):
    AGENCY = auto()
    MEDIA = auto()
    COM = auto()  # PR agency
    OTHER = auto()


class WireCommonMixin(IdMixin, LifeCycleMixin, Owned):
    @orm.declared_attr
    def title(cls):
        # title: Mapped[str] = mapped_column(default="")
        return mapped_column(String, default="")

    @orm.declared_attr
    def content(cls):
        # content: Mapped[str] = mapped_column(default="")
        return mapped_column(String, default="")

    @orm.declared_attr
    def summary(cls):
        # summary: Mapped[str] = mapped_column(default="")
        return mapped_column(String, default="")

    # Etat: Brouillon, Publié, Archivé
    status: Mapped[PostStatus] = mapped_column(Enum(PostStatus), default=DRAFT)

    published_at: Mapped[datetime | None] = mapped_column(
        ArrowType(timezone=True), nullable=True
    )
    last_updated_at: Mapped[datetime | None] = mapped_column(
        ArrowType(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        ArrowType(timezone=True), nullable=True
    )

    publisher_id: Mapped[int | None] = mapped_column(ForeignKey(Organisation.id))

    image_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    @orm.declared_attr
    def publisher(cls):
        return orm.relationship(Organisation, foreign_keys=[cls.publisher_id])

    # # Media
    # media_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey(Organisation.id))
    #
    # @orm.declared_attr
    # def media(cls):
    #     return orm.relationship(Organisation, foreign_keys=[cls.media_id])
    #
    # # Commanditaire
    # commanditaire_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey(User.id))
    #
    # # Titre
    # titre: Mapped[str] = mapped_column(default="")
    #
    # # Titre
    # brief: Mapped[str] = mapped_column(default="")
    #
    # # N° d’édition
    # numero_edition: Mapped[str] = mapped_column(default="")
    #
    # # Contenu
    # contenu: Mapped[str] = mapped_column(default="")
    #
    # # Type
    # type_contenu: Mapped[str] = mapped_column(default="")
    #
    # # Taille
    # taille_contenu: Mapped[str] = mapped_column(default="")


class NewsMetadataMixin:
    # NEWS-Genres
    genre: Mapped[str] = mapped_column(default="", use_existing_column=True)

    # NEWS-Rubriques
    section: Mapped[str] = mapped_column(default="", use_existing_column=True)

    # NEWS-Types d’info / "Thématique"
    topic: Mapped[str] = mapped_column(default="", use_existing_column=True)

    # NEWS-Secteurs
    sector: Mapped[str] = mapped_column(default="", use_existing_column=True)

    # Géo-localisation
    geo_localisation: Mapped[str] = mapped_column(default="", use_existing_column=True)

    # Langue
    language: Mapped[str] = mapped_column(default="fr", use_existing_column=True)

    # Temp
    country = ""
    region = ""
    city = ""


class Post(BaseContent, LifeCycleMixin):
    __mapper_args__: ClassVar[dict] = {
        "polymorphic_identity": "post",
    }

    title: Mapped[str] = mapped_column(default="", use_existing_column=True)
    content: Mapped[str] = mapped_column(default="", use_existing_column=True)
    summary: Mapped[str] = mapped_column(default="")

    # Etat: Brouillon, Publié, Archivé
    status: Mapped[PostStatus] = mapped_column(Enum(PostStatus), default=DRAFT)

    published_at: Mapped[datetime | None] = mapped_column(
        ArrowType(timezone=True), nullable=True
    )
    last_updated_at: Mapped[datetime | None] = mapped_column(
        ArrowType(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        ArrowType(timezone=True), nullable=True
    )

    publisher_id: Mapped[int | None] = mapped_column(ForeignKey(Organisation.id))

    image_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    @orm.declared_attr
    def publisher(cls):
        return orm.relationship(Organisation, foreign_keys=[cls.publisher_id])

    # # Media
    # media_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey(Organisation.id))
    #
    # @orm.declared_attr
    # def media(cls):
    #     return orm.relationship(Organisation, foreign_keys=[cls.media_id])
    #
    # # Commanditaire
    # commanditaire_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey(User.id))
    #
    # # Titre
    # titre: Mapped[str] = mapped_column(default="")
    #
    # # Titre
    # brief: Mapped[str] = mapped_column(default="")
    #
    # # N° d’édition
    # numero_edition: Mapped[str] = mapped_column(default="")
    #
    # # Contenu
    # contenu: Mapped[str] = mapped_column(default="")
    #
    # # Type
    # type_contenu: Mapped[str] = mapped_column(default="")
    #
    # # Taille
    # taille_contenu: Mapped[str] = mapped_column(default="")


class ArticlePost(NewsMetadataMixin, Post, Taggable):
    __mapper_args__: ClassVar[dict] = {
        "polymorphic_identity": "article",
    }

    # id of the corresponding newsroom article (if any)
    newsroom_id: Mapped[int | None] = mapped_column(
        BigInteger, index=True, nullable=True
    )

    publisher_type: Mapped[PublisherType] = mapped_column(
        Enum(PublisherType), default=PublisherType.MEDIA
    )


class PressReleasePost(NewsMetadataMixin, Post, Taggable):
    __mapper_args__: ClassVar[dict] = {
        "polymorphic_identity": "press_release",
    }

    # id of the corresponding com'room communique (if any)
    newsroom_id: Mapped[int | None] = mapped_column(
        BigInteger, index=True, nullable=True, use_existing_column=True
    )

    publisher_type: Mapped[PublisherType] = mapped_column(
        Enum(PublisherType), default=PublisherType.COM, use_existing_column=True
    )
