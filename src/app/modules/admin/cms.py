# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin mini-CMS — model, repository and service for corporate pages.

Backs the public `/page/<slug>` route (CGV, confidentialité,
« Notre offre », etc.) with an admin editing surface at
`/admin/cms`. Spec: `local-notes/specs/corporate-pages-cms.md`.
"""

from __future__ import annotations

from flask_super.decorators import service
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from svcs.flask import container

from app.models.auth import User
from app.models.base import Base
from app.models.mixins import IdMixin, Timestamped
from app.services.repositories import Repository


class CorporatePage(IdMixin, Timestamped, Base):
    """A single editable corporate page (CGV, confidentialité, etc.).

    The `slug` column is the stable identifier used in public URLs
    (`/page/<slug>`). It's unique and indexed — the public route
    looks it up with a single equality query.
    """

    __tablename__ = "cms_corporate_page"

    slug: Mapped[str] = mapped_column(String, unique=True, index=True)
    title: Mapped[str] = mapped_column(String, default="")
    body_md: Mapped[str] = mapped_column(Text, default="")

    updated_by_id: Mapped[int | None] = mapped_column(
        ForeignKey(User.id, ondelete="SET NULL"),
        nullable=True,
    )
    updated_by: Mapped[User | None] = relationship(
        User, foreign_keys=[updated_by_id]
    )


@service
class CorporatePageRepository(Repository[CorporatePage]):
    model_type = CorporatePage


@service
class CorporatePageService:
    """CRUD wrapper around CorporatePageRepository."""

    def get(self, slug: str) -> CorporatePage | None:
        repo = container.get(CorporatePageRepository)
        return repo.get_one_or_none(slug=slug)

    def list_all(self) -> list[CorporatePage]:
        repo = container.get(CorporatePageRepository)
        return list(repo.list())

    def upsert(
        self,
        slug: str,
        title: str,
        body_md: str,
        updated_by: User | None = None,
    ) -> CorporatePage:
        repo = container.get(CorporatePageRepository)
        page = repo.get_one_or_none(slug=slug)
        if page is None:
            page = CorporatePage(slug=slug, title=title, body_md=body_md)
        else:
            page.title = title
            page.body_md = body_md
        if updated_by is not None:
            page.updated_by_id = updated_by.id
        repo.add(page)
        repo.session.flush()
        return page
