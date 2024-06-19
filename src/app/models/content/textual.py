# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import TextEditorialContent


class Article(TextEditorialContent):
    __tablename__ = "edt_article"

    id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey(TextEditorialContent.id), primary_key=True
    )

    subheader: Mapped[str] = mapped_column(default="", info={"group": "header"})

    image_id: Mapped[str] = mapped_column(default="", info={"group": "header"})
    image_caption: Mapped[str] = mapped_column(default="", info={"group": "header"})
    image_copyright: Mapped[str] = mapped_column(default="", info={"group": "header"})
    image_url: Mapped[str] = mapped_column(default="", info={"group": "header"})

    subject: Mapped[str] = mapped_column(default="", info={"group": "metadata"})
    copyright: Mapped[str] = mapped_column(default="", info={"group": "metadata"})

    # FIXME: backward compatibility hack
    topic: str = ""
    job: str = ""
    competency: str = ""

    class Meta:
        type_id = "article"
        type_label = "Article"
        description = "Article"

        searchable_cols = [*TextEditorialContent.Meta.searchable_cols, "subheader"]

        groups = {
            "header": ["subheader", "image_url"],
        }

    def to_json_ld(self):
        return {
            "@context": "https://schema.org",
            "@type": "Article",
            "name": self.title,
            "publisher": "AIpress24",
            "datePosted": self.created_at.isoformat(),
            "description": self.subheader,
        }
