# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import arrow
import sqlalchemy as sa
from arrow import Arrow
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy_utils import ArrowType

from app.models.content.base import BaseContent
from app.models.content.mixins import ClassificationMixin, Publishable, Searchable
from app.models.mixins import Addressable
from app.services.tagging.interfaces import Taggable


class PressRelease(
    BaseContent, ClassificationMixin, Publishable, Taggable, Searchable, Addressable
):
    __tablename__ = "com_press_release"

    id: Mapped[int] = mapped_column(sa.ForeignKey(BaseContent.id), primary_key=True)

    # Inherited:
    # - title
    # - content
    # - summary

    # "About us" section
    about: Mapped[str] = mapped_column(default="", info={"group": "contents"})

    release_datetime: Mapped[Arrow] = mapped_column(
        ArrowType, default=arrow.now, info={"group": "dates"}
    )
    embargo_datetime: Mapped[Arrow] = mapped_column(
        ArrowType, default=arrow.now, info={"group": "dates"}
    )

    image_url: Mapped[str] = mapped_column(default="", info={"group": "header"})

    # TODO:
    # +attachments: list[Attachment]

    # TODO: should be URI
    # url = sa.Column(sa.UnicodeText, nullable=False, default="")

    class Meta:
        groups = {
            "contents": ["about"],
            "dates": ["release_datetime", "embargo_datetime"],
            "header": ["image_url"],
        }
