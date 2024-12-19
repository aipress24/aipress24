# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from datetime import datetime

from aenum import StrEnum, auto
from sqlalchemy import BigInteger, Column, Enum, ForeignKey, Integer, orm
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy_utils import ArrowType

from app.models.base import Base
from app.models.mixins import IdMixin, LifeCycleMixin, Owned
from app.models.organisation import Organisation


class PostStatus(StrEnum):
    DRAFT = auto()
    PUBLIC = auto()
    ARCHIVED = auto()


class WireCommonMixin(IdMixin, LifeCycleMixin, Owned):
    title: Mapped[str] = mapped_column(default="")
    content: Mapped[str] = mapped_column(default="")
    summary: Mapped[str] = mapped_column(default="")

    # Etat: Brouillon, Publié, Archivé
    status: Mapped[PostStatus] = mapped_column(
        Enum(PostStatus), default=PostStatus.DRAFT
    )

    published_at: Mapped[datetime | None] = mapped_column(ArrowType, nullable=True)
    last_updated_at: Mapped[datetime | None] = mapped_column(ArrowType, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(ArrowType, nullable=True)

    publisher_id: Mapped[int | None] = mapped_column(ForeignKey(Organisation.id))

    image_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # image_caption: Mapped[str] = mapped_column(default="")
    # image_copyright: Mapped[str] = mapped_column(default="")
    # image_url: Mapped[str] = mapped_column(default="")

    @orm.declared_attr
    def publisher(cls):
        return orm.relationship(Organisation, foreign_keys=[cls.publisher_id])

    # # Media
    # media_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey(Organisation.id))
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
    #
    # @orm.declared_attr
    # def media(cls):
    #     return orm.relationship(Organisation, foreign_keys=[cls.media_id])


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

    # Temp
    country = ""
    region = ""
    city = ""


class UserFeedbackMixin:
    @orm.declared_attr
    def view_count(cls):
        return Column(Integer, nullable=False, default=0)

    @orm.declared_attr
    def like_count(cls):
        return Column(Integer, nullable=False, default=0)

    @orm.declared_attr
    def comment_count(cls):
        return Column(Integer, nullable=False, default=0)

    # view_count: Mapped[int] = mapped_column(default=0)
    # like_count: Mapped[int] = mapped_column(default=0)
    # comment_count: Mapped[int] = mapped_column(default=0)


class ArticlePost(WireCommonMixin, NewsMetadataMixin, UserFeedbackMixin, Base):
    __tablename__ = "wir_article"

    # id of the corresponding newsroom article (if any)
    newsroom_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # newsroom_id: Mapped[int] = mapped_column(ForeignKey("nrm_article.id"), nullable=True)
