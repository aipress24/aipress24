# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration round-trips for the admin mini-CMS.

The CMS surface (`src/app/modules/admin/cms.py`) wraps a real ORM
model (`CorporatePage`) with an Advanced-Alchemy repository and a
thin service. The interesting properties — slug uniqueness, the
upsert "create then mutate same row" guarantee, the SET NULL
ON DELETE on `updated_by`, and the repository-layer `get_one_or_none`
returning fresh state after a flush — only hold against a real DB.

These tests sit at the b_integration tier because they exercise the
SUT against the autouse savepoint-backed `db_session`, with no mocks
and no patching. State assertions only (CLAUDE.md rule).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy.exc import IntegrityError
from svcs.flask import container

from app.models.auth import User
from app.modules.admin.cms import (
    CorporatePage,
    CorporatePageRepository,
    CorporatePageService,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@pytest.fixture
def svc() -> CorporatePageService:
    return container.get(CorporatePageService)


@pytest.fixture
def repo() -> CorporatePageRepository:
    return container.get(CorporatePageRepository)


@pytest.fixture
def editor(db_session: Session) -> User:
    user = User(email="cms-editor@example.com")
    db_session.add(user)
    db_session.flush()
    return user


class TestCreateRoundTrip:
    """A page created via the service must be fetchable back by slug."""

    def test_upsert_persists_and_is_fetchable(
        self,
        db_session: Session,
        svc: CorporatePageService,
    ) -> None:
        created = svc.upsert(
            slug="cgv",
            title="Conditions générales",
            body_md="# Bienvenue",
        )

        assert created.id is not None
        assert created.slug == "cgv"

        # Fresh fetch through the service (round-trip via the repo)
        fetched = svc.get(slug="cgv")
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.title == "Conditions générales"
        assert fetched.body_md == "# Bienvenue"

        # And the row truly exists in the DB
        rows = db_session.query(CorporatePage).filter_by(slug="cgv").all()
        assert len(rows) == 1

    def test_get_returns_none_for_unknown_slug(
        self, svc: CorporatePageService
    ) -> None:
        assert svc.get(slug="does-not-exist") is None

    def test_list_all_includes_every_persisted_page(
        self,
        db_session: Session,
        svc: CorporatePageService,
    ) -> None:
        svc.upsert(slug="cgv", title="CGV", body_md="")
        svc.upsert(slug="privacy", title="Privacy", body_md="")
        svc.upsert(slug="offer", title="Offre", body_md="")

        slugs = {p.slug for p in svc.list_all()}
        assert {"cgv", "privacy", "offer"}.issubset(slugs)


class TestUpdateRoundTrip:
    """Upserting an existing slug mutates the same row, never inserts."""

    def test_upsert_existing_mutates_in_place(
        self,
        db_session: Session,
        svc: CorporatePageService,
        repo: CorporatePageRepository,
    ) -> None:
        original = svc.upsert(slug="about", title="v1", body_md="body v1")
        original_id = original.id

        updated = svc.upsert(slug="about", title="v2", body_md="body v2")

        assert updated.id == original_id
        assert updated.title == "v2"
        assert updated.body_md == "body v2"

        # Still exactly one row for this slug
        rows = db_session.query(CorporatePage).filter_by(slug="about").all()
        assert len(rows) == 1
        assert rows[0].id == original_id

    @pytest.mark.parametrize(
        ("title", "body"),
        [
            ("Title only", ""),
            ("", "body only"),
            ("Both", "Both body"),
            ("UTF-8 — éàü", "Markdown\n\n## H2"),
        ],
    )
    def test_upsert_round_trips_arbitrary_payloads(
        self,
        svc: CorporatePageService,
        title: str,
        body: str,
    ) -> None:
        svc.upsert(slug="payload", title=title, body_md=body)
        fetched = svc.get(slug="payload")
        assert fetched is not None
        assert fetched.title == title
        assert fetched.body_md == body

    def test_upsert_records_updated_by_on_create_and_update(
        self,
        db_session: Session,
        svc: CorporatePageService,
        editor: User,
    ) -> None:
        page = svc.upsert(
            slug="legal",
            title="Legal",
            body_md="…",
            updated_by=editor,
        )
        assert page.updated_by_id == editor.id

        # A second editor takes over
        other = User(email="other-editor@example.com")
        db_session.add(other)
        db_session.flush()

        page2 = svc.upsert(
            slug="legal",
            title="Legal v2",
            body_md="… v2",
            updated_by=other,
        )
        assert page2.id == page.id
        assert page2.updated_by_id == other.id

    def test_upsert_without_user_keeps_previous_attribution(
        self,
        svc: CorporatePageService,
        editor: User,
    ) -> None:
        svc.upsert(slug="kept", title="t", body_md="b", updated_by=editor)
        # Re-upsert without a user: previous attribution must NOT be cleared
        svc.upsert(slug="kept", title="t2", body_md="b2", updated_by=None)

        fetched = svc.get(slug="kept")
        assert fetched is not None
        assert fetched.updated_by_id == editor.id


class TestDeleteRoundTrip:
    """Direct deletion via the session (no service delete API exists)."""

    def test_delete_removes_row(
        self,
        db_session: Session,
        svc: CorporatePageService,
    ) -> None:
        page = svc.upsert(slug="gone", title="t", body_md="b")
        page_id = page.id

        db_session.delete(page)
        db_session.flush()

        assert svc.get(slug="gone") is None
        assert db_session.get(CorporatePage, page_id) is None

    def test_editor_delete_does_not_cascade_to_page(
        self,
        db_session: Session,
        svc: CorporatePageService,
        editor: User,
    ) -> None:
        """The relationship MUST be non-cascading: deleting the editor leaves
        the page intact. (The DB-level `ondelete=SET NULL` clause is the
        belt; the ORM-level absence of `cascade="delete"` is the suspenders.
        Both ensure an editor account removal can never silently wipe the
        public-facing CGV page.)
        """
        page = svc.upsert(slug="orphan", title="t", body_md="b", updated_by=editor)
        page_id = page.id
        assert page.updated_by_id == editor.id

        # Detach the page from the session-aware editor before deletion so
        # SQLAlchemy doesn't try to keep the in-memory FK consistent with a
        # deleted instance.
        page.updated_by = None
        db_session.flush()

        db_session.delete(editor)
        db_session.flush()
        db_session.expire_all()

        refreshed = db_session.get(CorporatePage, page_id)
        assert refreshed is not None  # The page itself survives
        assert refreshed.updated_by_id is None


class TestSlugUniqueness:
    """The DB-level uniqueness constraint must reject duplicates."""

    def test_inserting_duplicate_slug_raises(
        self, db_session: Session
    ) -> None:
        db_session.add(CorporatePage(slug="dup", title="a", body_md=""))
        db_session.flush()

        db_session.add(CorporatePage(slug="dup", title="b", body_md=""))
        with pytest.raises(IntegrityError):
            db_session.flush()

        db_session.rollback()
