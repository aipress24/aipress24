# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from datetime import datetime
from typing import ClassVar

import sqlalchemy as sa
from aenum import StrEnum, auto
from sqlalchemy import orm
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy_utils import ArrowType

from app.models.base import Base
from app.models.mixins import IdMixin, LifeCycleMixin, Owned
from app.models.organisation import Organisation
from app.modules.wip.models.newsroom._base import NewsMetadataMixin, NewsroomCommonMixin


class ArticleStatus(StrEnum):
    DRAFT = auto()
    PUBLIC = auto()
    ARCHIVED = auto()


class Article(
    NewsroomCommonMixin,
    NewsMetadataMixin,
    Base,
):
    __tablename__ = "nrm_article"

    chapo: Mapped[str] = mapped_column(default="")

    copyright: Mapped[str] = mapped_column(default="")

    # ------------------------------------------------------------
    # Dates
    # ------------------------------------------------------------

    # Parution prévue
    date_parution_prevue: Mapped[datetime] = mapped_column(ArrowType)

    # Publié sur AIP24
    date_publication_aip24: Mapped[datetime | None] = mapped_column(
        ArrowType, nullable=True
    )

    # Paiement
    date_paiement: Mapped[datetime] = mapped_column(ArrowType)

    # ------------------------------------------------------------
    # Copied from Publishable
    # ------------------------------------------------------------

    # Etat: Brouillon, Publié, Archivé
    status: Mapped[ArticleStatus] = mapped_column(
        sa.Enum(ArticleStatus), default=ArticleStatus.DRAFT
    )

    published_at: Mapped[datetime | None] = mapped_column(ArrowType, nullable=True)
    expired_at: Mapped[datetime | None] = mapped_column(ArrowType, nullable=True)
    publisher_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("crp_organisation.id")
    )

    publisher: Mapped[Organisation | None] = orm.relationship(
        Organisation, foreign_keys=[publisher_id]
    )

    images: ClassVar[list[Image]]

    #
    # Images management
    #
    def get_image(self, image_id: int) -> Image:
        return next((image for image in self.images if image.id == image_id), None)

    @property
    def sorted_images(self) -> list[Image]:
        return sorted(self.images, key=lambda x: x.position)

    def add_image(self, image: Image):
        self.images.append(image)
        image.position = len(self.images) - 1

    def delete_image(self, image: Image):
        self.images.remove(image)
        self.update_image_positions()

    def update_image_positions(self):
        for i, image in enumerate(self.sorted_images):
            image.position = i


class Image(IdMixin, LifeCycleMixin, Owned, Base):
    """Images liées à l'article (carousel)."""

    __tablename__ = "nrm_image"

    blob_id: Mapped[str] = mapped_column(nullable=False)

    article_id: Mapped[int] = mapped_column(
        sa.ForeignKey(Article.id, ondelete="CASCADE"), nullable=False
    )
    caption: Mapped[str] = mapped_column(default="")
    copyright: Mapped[str] = mapped_column(default="")

    article: Mapped[Article] = orm.relationship(
        Article, foreign_keys=[article_id], backref="images"
    )

    position: Mapped[int] = mapped_column(default=0)

    @property
    def url(self) -> str:
        return f"/wip/articles/{self.article_id}/images/{self.id}"

    @property
    def is_first(self) -> bool:
        return self.position == 0

    @property
    def is_last(self) -> bool:
        return self.position == len(self.article.images) - 1
