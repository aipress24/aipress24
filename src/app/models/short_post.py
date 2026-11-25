# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""ShortPost model (wall post)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

import arrow
import sqlalchemy as sa
from advanced_alchemy.types.file_object import FileObject, StoredObject
from markupsafe import escape
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy_utils import ArrowType

from app.lib.file_object_utils import media_url
from app.lib.html import remove_markup
from app.lib.urls import web_url
from app.models.base import Base
from app.models.base_content import BaseContent
from app.models.mixins import IdMixin, LifeCycleMixin
from app.services.html_sanitize import SanitizedHTML


class ShortPost(BaseContent, LifeCycleMixin, Base):
    """A message on the wall: plain text, and images."""

    __mapper_args__ = {
        "polymorphic_identity": "short_post",
    }

    # Carry the SanitizedHTML type from BaseContent forward — the
    # `use_existing_column=True` redeclaration would otherwise drop
    # it and let raw HTML reach the DB. Read and write `text` instead.
    content: Mapped[str] = mapped_column(
        SanitizedHTML, default="", use_existing_column=True
    )

    # In the past for a message first published on another network.
    published_at: Mapped[arrow.Arrow | None] = mapped_column(
        ArrowType(timezone=True), nullable=True, use_existing_column=True
    )

    # What an API client calls the message this one comes from, as its URL.
    external_ref: Mapped[str | None] = mapped_column(sa.String(500))

    images: Mapped[list[ShortPostImage]] = relationship(
        order_by="ShortPostImage.position",
        cascade="all, delete-orphan",
        back_populates="post",
    )

    def __init__(self, **kw: Any) -> None:
        kw.setdefault("published_at", arrow.utcnow())
        super().__init__(**kw)

    @property
    def text(self) -> str:
        """The plain text of the message."""
        return remove_markup(self.content or "")

    @text.setter
    def text(self, value: str) -> None:
        self.content = str(escape(value))

    @property
    def date(self) -> arrow.Arrow:
        """When it was published: a post of before `published_at` has none."""
        return arrow.get(self.published_at or self.created_at)

    @property
    def original_url(self) -> str:
        """Where the message was first published, if elsewhere."""
        return web_url(self.external_ref)

    @property
    def original_host(self) -> str:
        return urlsplit(self.original_url).netloc


class ShortPostImage(IdMixin, Base):
    """An image of a wall post."""

    __tablename__ = "soc_post_image"

    post_id: Mapped[int] = mapped_column(
        sa.ForeignKey(BaseContent.id, ondelete="CASCADE"), index=True
    )
    content: Mapped[FileObject | None] = mapped_column(
        StoredObject(backend="s3"), nullable=True
    )
    caption: Mapped[str] = mapped_column(default="")
    position: Mapped[int] = mapped_column(default=0)

    post: Mapped[ShortPost] = relationship(back_populates="images")

    @property
    def url(self) -> str:
        return media_url(self.content)


# Deleting a message frees its reference. On the table, as a subclass which
# shares it has no arguments of its own.
sa.Index(
    "ix_frt_content_owner_external_ref",
    ShortPost.owner_id,
    ShortPost.external_ref,
    unique=True,
    postgresql_where=sa.text("deleted_at IS NULL"),
    sqlite_where=sa.text("deleted_at IS NULL"),
)
