# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import ClassVar

from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from app.lib.names import to_snake_case
from app.models.base import Base
from app.models.mixins import IdMixin, LifeCycleMixin, Owned
from app.services.html_sanitize import SanitizedHTML

# -----------------------------------------------------------------
# Main abstract classes (PlantUML-flavored diagram)
# -----------------------------------------------------------------
#
# abstract class BaseContent {
#     +creators: list[Person]
#     +contributors: list[Person]
#
#     +date_created: DateTime
#     +date_modified: DateTime
#
#     +keywords: list[String]
# }
# note left: "Classe de base de tous les contenus de l'application"
#
# abstract class EditorialContent {
#     +copyright_holder: string
#     +copyright_notice: string
#
#     +title: string
#     +pub_status: string
#
#     +genres: set[string]
#     +language: string
#
#     +url: URI
#     +info_source: URI
# }
# EditorialContent -up-|> BaseContent
#
# abstract class TextEditorialContent {
#     +content: HTML
# }
# TextEditorialContent -up-|> EditorialContent


# Abstract
class BaseContent(IdMixin, LifeCycleMixin, Owned, Base):
    __tablename__ = "cnt_base"

    type: Mapped[str] = mapped_column()

    @classmethod
    def get_type_id(cls) -> str:
        return to_snake_case(cls.__name__)

    @declared_attr
    def __mapper_args__(cls):
        return {
            "polymorphic_identity": cls.get_type_id(),
            "polymorphic_on": cls.type,
        }

    title: Mapped[str] = mapped_column(default="")
    # Sanitize HTML on write — covers every polymorphic subclass
    # (ArticlePost, PressReleasePost, EventPost, ShortPost, Comment,
    # …). For subclasses whose content is plain text, this is a
    # no-op; for HTML-bearing ones (Trix-rendered articles, comments,
    # event bodies) it neutralises script/event-handler injection
    # before the row ever reaches the DB.
    content: Mapped[str] = mapped_column(SanitizedHTML, default="")
    summary: Mapped[str] = mapped_column(default="")
    url: Mapped[str] = mapped_column(default="")

    class Meta:
        searchable_cols: ClassVar = ["title", "content", "summary"]

    # TODO
    # +creators: list[Person]
    # +contributors: list[Person]
    # +status ?

    def __repr__(self) -> str:
        title = self.title or ""
        if len(title) > 20:
            title = title[0:20] + ".."
        return f"<{self.__class__.__name__} id={self.id} title={title!r}>"
