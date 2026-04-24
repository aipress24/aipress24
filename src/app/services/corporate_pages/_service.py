# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask_super.decorators import service
from svcs.flask import container

from app.models.auth import User

from ._models import CorporatePage, CorporatePageRepository


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
