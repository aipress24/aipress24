# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from svcs.flask import container

from app.models.auth import User
from app.services.corporate_pages import (
    CorporatePage,
    CorporatePageRepository,
    CorporatePageService,
)

if TYPE_CHECKING:
    from flask_sqlalchemy import SQLAlchemy


def test_upsert_creates_new(db: SQLAlchemy) -> None:
    svc = container.get(CorporatePageService)
    page = svc.upsert(slug="cgv", title="CGV", body_md="# Hello")
    db.session.flush()

    assert page.slug == "cgv"
    assert page.title == "CGV"
    assert page.body_md == "# Hello"
    assert page.id is not None


def test_upsert_updates_existing(db: SQLAlchemy) -> None:
    svc = container.get(CorporatePageService)
    svc.upsert(slug="cgv", title="CGV v1", body_md="v1 body")
    db.session.flush()

    updated = svc.upsert(slug="cgv", title="CGV v2", body_md="v2 body")
    db.session.flush()

    assert updated.title == "CGV v2"
    assert updated.body_md == "v2 body"

    # Still a single row
    repo = container.get(CorporatePageRepository)
    assert len(list(repo.list())) == 1


def test_upsert_records_updated_by(db: SQLAlchemy) -> None:
    user = User(email="editor@example.com")
    db.session.add(user)
    db.session.flush()

    svc = container.get(CorporatePageService)
    page = svc.upsert(
        slug="a-propos",
        title="A propos",
        body_md="body",
        updated_by=user,
    )
    db.session.flush()

    assert page.updated_by_id == user.id


def test_get_returns_none_when_missing(db: SQLAlchemy) -> None:
    svc = container.get(CorporatePageService)
    assert svc.get(slug="nope") is None


def test_slug_uniqueness(db: SQLAlchemy) -> None:
    db.session.add(CorporatePage(slug="cgv", title="t1", body_md=""))
    db.session.flush()

    db.session.add(CorporatePage(slug="cgv", title="t2", body_md=""))
    with pytest.raises(Exception):  # IntegrityError wrapped
        db.session.flush()
    db.session.rollback()
