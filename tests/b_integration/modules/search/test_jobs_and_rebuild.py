# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests covering the index ⇄ database loop.

Exercises three end-to-end flows:

* ``reindex_from_source`` upserts a public post into the index.
* ``reindex_from_source`` removes a post from the index once it stops
  being public (covers the unpublish path).
* ``flask search rebuild`` walks the database and produces an index
  that contains exactly the currently-public posts.

These tests skip Dramatiq's broker entirely — we call the wrapped
function directly. The receiver-to-job wiring is covered by a unit
test of its own; here we focus on the job's interaction with the DB
and the engine.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
import svcs.flask
from wesh.backends.filedb.filestore import RamStorage

from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.biz.models import JobOffer, MissionOffer
from app.modules.search.cli import rebuild
from app.modules.search.engine import SearchEngine
from app.modules.search.jobs import reindex_from_source
from app.modules.swork.models import Group
from app.modules.wire.models import ArticlePost, PressReleasePost

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def test_engine(app) -> Iterator[SearchEngine]:
    """A RAM-backed engine swapped into the SVCS container for the
    duration of the test. Lets us inspect the index without committing
    anything to the app's database.
    """
    engine = SearchEngine(RamStorage())
    previous = svcs.flask.overwrite_value(SearchEngine, engine)
    try:
        yield engine
    finally:
        if previous is not None:
            svcs.flask.overwrite_value(SearchEngine, previous)


def _make_article_post(db_session, *, status, newsroom_id, **fields) -> ArticlePost:
    user = User(email=f"u{newsroom_id}@example.com")
    db_session.add(user)
    db_session.flush()
    post = ArticlePost(
        owner=user,
        status=status,
        published_at=fields.pop(
            "published_at", datetime(2026, 1, 1, tzinfo=UTC)
        ),
        **fields,
    )
    post.newsroom_id = newsroom_id
    db_session.add(post)
    db_session.flush()
    return post


def _make_press_release(db_session, *, status, newsroom_id, **fields) -> PressReleasePost:
    user = User(email=f"pr{newsroom_id}@example.com")
    db_session.add(user)
    db_session.flush()
    post = PressReleasePost(
        owner=user,
        status=status,
        published_at=fields.pop(
            "published_at", datetime(2026, 1, 1, tzinfo=UTC)
        ),
        **fields,
    )
    post.newsroom_id = newsroom_id
    db_session.add(post)
    db_session.flush()
    return post


class TestReindexFromSource:
    def test_public_article_is_indexed(self, app, db_session, test_engine):
        with app.test_request_context():
            _make_article_post(
                db_session,
                status=PublicationStatus.PUBLIC,
                newsroom_id=101,
                title="Hello search",
                content="Some body content about Python.",
                summary="A tiny summary.",
            )

            reindex_from_source.fn("article", 101)

            hits = test_engine.search("Python")
            assert len(hits) == 1
            assert hits[0]["type"] == "article"
            assert hits[0]["title"] == "Hello search"

    def test_draft_article_is_not_indexed(self, app, db_session, test_engine):
        with app.test_request_context():
            _make_article_post(
                db_session,
                status=PublicationStatus.DRAFT,
                newsroom_id=102,
                title="Secret draft",
                content="Not visible yet.",
            )

            reindex_from_source.fn("article", 102)

            assert test_engine.search("Secret") == []

    def test_unpublish_removes_doc(self, app, db_session, test_engine):
        with app.test_request_context():
            post = _make_article_post(
                db_session,
                status=PublicationStatus.PUBLIC,
                newsroom_id=103,
                title="Will be retracted",
                content="Body.",
            )
            reindex_from_source.fn("article", 103)
            assert test_engine.search("retracted")  # warm-up — it is in

            post.status = PublicationStatus.DRAFT
            db_session.flush()

            reindex_from_source.fn("article", 103)

            assert test_engine.search("retracted") == []

    def test_missing_source_is_noop(self, app, db_session, test_engine):
        """No ArticlePost mirror exists for source_id=999. The job must
        not crash — it just skips."""
        with app.test_request_context():
            reindex_from_source.fn("article", 999)
            assert test_engine.search("anything") == []

    def test_press_release_is_indexed_with_correct_type(
        self, app, db_session, test_engine
    ):
        with app.test_request_context():
            _make_press_release(
                db_session,
                status=PublicationStatus.PUBLIC,
                newsroom_id=201,
                title="Press release one",
                content="Body.",
            )

            reindex_from_source.fn("press_release", 201)

            hits = test_engine.search("Press release one")
            assert len(hits) == 1
            assert hits[0]["type"] == "press_release"

    def test_unknown_source_type_raises(self, app, test_engine):
        with app.test_request_context(), pytest.raises(ValueError, match="Unknown"):
            reindex_from_source.fn("unknown_kind", 1)


def _make_mission_offer(db_session, *, status, **fields) -> MissionOffer:
    user = User(email=f"u_mission_{fields.get('title', 'x')}@example.com")
    db_session.add(user)
    db_session.flush()
    offer = MissionOffer(owner=user, status=status, **fields)
    db_session.add(offer)
    db_session.flush()
    return offer


class TestReindexFromSourceMarketplace:
    def test_public_mission_is_indexed(self, app, db_session, test_engine):
        with app.test_request_context():
            offer = _make_mission_offer(
                db_session,
                status=PublicationStatus.PUBLIC,
                title="Investigation",
                description="Enquête sur la fiscalité.",
            )

            reindex_from_source.fn("marketplace", offer.id)

            hits = test_engine.search("fiscalité")
            assert len(hits) == 1
            assert hits[0]["type"] == "mission_offer"
            assert hits[0]["title"] == "Investigation"

    def test_pending_mission_is_not_indexed(self, app, db_session, test_engine):
        with app.test_request_context():
            offer = _make_mission_offer(
                db_session,
                status=PublicationStatus.PENDING,
                title="Awaiting moderation",
                description="Hidden body.",
            )

            reindex_from_source.fn("marketplace", offer.id)

            assert test_engine.search("Hidden") == []

    def test_rejected_mission_is_not_indexed(self, app, db_session, test_engine):
        with app.test_request_context():
            offer = _make_mission_offer(
                db_session,
                status=PublicationStatus.REJECTED,
                title="Rejected",
                description="Rejected body.",
            )

            reindex_from_source.fn("marketplace", offer.id)

            assert test_engine.search("Rejected body") == []

    def test_status_flip_removes_from_index(
        self, app, db_session, test_engine
    ):
        with app.test_request_context():
            offer = _make_mission_offer(
                db_session,
                status=PublicationStatus.PUBLIC,
                title="Live",
                description="indexed body marketplaceflip",
            )
            reindex_from_source.fn("marketplace", offer.id)
            assert test_engine.search("marketplaceflip")

            offer.status = PublicationStatus.REJECTED
            db_session.flush()
            reindex_from_source.fn("marketplace", offer.id)

            assert test_engine.search("marketplaceflip") == []

    def test_job_offer_uses_polymorphic_loading(
        self, app, db_session, test_engine
    ):
        """Source type ``marketplace`` resolves to ``MarketplaceContent``
        and polymorphic loading returns the concrete subclass — the
        adapter then computes the right ``job_offer`` discriminator.
        """
        with app.test_request_context():
            user = User(email="jobber@example.com")
            db_session.add(user)
            db_session.flush()
            job = JobOffer(
                owner=user,
                title="Rédacteur en chef",
                description="Poste senior à Paris",
                status=PublicationStatus.PUBLIC,
            )
            db_session.add(job)
            db_session.flush()

            reindex_from_source.fn("marketplace", job.id)

            hits = test_engine.search("senior")
            assert len(hits) == 1
            assert hits[0]["type"] == "job_offer"


class TestReindexFromSourceGroup:
    def test_public_group_is_indexed(self, app, db_session, test_engine):
        with app.test_request_context():
            owner = User(email="group_owner@example.com")
            db_session.add(owner)
            db_session.flush()
            group = Group(
                name="Cercle des journalistes",
                description="Échange professionnel.",
                privacy="public",
                owner=owner,
            )
            db_session.add(group)
            db_session.flush()

            reindex_from_source.fn("group", group.id)

            hits = test_engine.search("Cercle")
            assert len(hits) == 1
            assert hits[0]["type"] == "group"

    def test_private_group_is_not_indexed(self, app, db_session, test_engine):
        with app.test_request_context():
            owner = User(email="private_group_owner@example.com")
            db_session.add(owner)
            db_session.flush()
            group = Group(
                name="Hidden",
                description="Caché.",
                privacy="private",
                owner=owner,
            )
            db_session.add(group)
            db_session.flush()

            reindex_from_source.fn("group", group.id)

            assert test_engine.search("Hidden") == []


class TestReindexFromSourceUser:
    def test_validated_user_is_indexed(self, app, db_session, test_engine):
        with app.test_request_context():
            user = User(
                email="indexed_user@example.com",
                first_name="Marie",
                last_name="Dupont",
                active=True,
                validated_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
            db_session.add(user)
            db_session.flush()

            reindex_from_source.fn("user", user.id)

            hits = test_engine.search("Marie")
            assert len(hits) == 1
            assert hits[0]["type"] == "user"
            assert hits[0]["title"] == "Marie Dupont"

    def test_unvalidated_user_is_not_indexed(
        self, app, db_session, test_engine
    ):
        with app.test_request_context():
            user = User(
                email="pending_user@example.com",
                first_name="Pierre",
                last_name="Notyetvalidated",
                active=True,
                validated_at=None,
            )
            db_session.add(user)
            db_session.flush()

            reindex_from_source.fn("user", user.id)

            assert test_engine.search("Notyetvalidated") == []


class TestReindexFromSourceOrganisation:
    def test_active_org_is_indexed(self, app, db_session, test_engine):
        with app.test_request_context():
            org = Organisation(name="Le Quotidien Test", active=True)
            org.bw_name = "Média"
            db_session.add(org)
            db_session.flush()

            reindex_from_source.fn("organisation", org.id)

            hits = test_engine.search("Quotidien")
            assert len(hits) == 1
            assert hits[0]["type"] == "organisation"

    def test_inactive_org_is_not_indexed(self, app, db_session, test_engine):
        with app.test_request_context():
            org = Organisation(name="Deactivated Inc", active=False)
            db_session.add(org)
            db_session.flush()

            reindex_from_source.fn("organisation", org.id)

            assert test_engine.search("Deactivated") == []

    def test_active_then_deactivated_removes_from_index(
        self, app, db_session, test_engine
    ):
        with app.test_request_context():
            org = Organisation(name="LifecycleCorp", active=True)
            db_session.add(org)
            db_session.flush()

            reindex_from_source.fn("organisation", org.id)
            assert test_engine.search("LifecycleCorp")

            org.active = False
            db_session.flush()
            reindex_from_source.fn("organisation", org.id)

            assert test_engine.search("LifecycleCorp") == []


class TestRebuildCli:
    def test_rebuild_indexes_only_public_posts(
        self, app, db_session, test_engine
    ):
        """``flask search rebuild`` should clear the index and then
        re-walk the database, keeping only public posts.
        """
        with app.test_request_context():
            _make_article_post(
                db_session,
                status=PublicationStatus.PUBLIC,
                newsroom_id=301,
                title="Public article",
                content="Findable body.",
            )
            _make_article_post(
                db_session,
                status=PublicationStatus.DRAFT,
                newsroom_id=302,
                title="Draft article",
                content="Hidden body.",
            )
            _make_press_release(
                db_session,
                status=PublicationStatus.PUBLIC,
                newsroom_id=303,
                title="Public PR",
                content="PR body.",
            )

            # Pre-populate the index with a stale doc that should
            # disappear after the rebuild.
            test_engine.upsert(
                {
                    "type": "article",
                    "id": "article:9999",
                    "title": "Stale",
                    "text": "stale stale stale",
                    "summary": "",
                    "url": "/x",
                    "timestamp": datetime(2020, 1, 1, tzinfo=UTC),
                    "tags": "",
                }
            )

            runner = app.test_cli_runner()
            result = runner.invoke(rebuild)
            assert result.exit_code == 0, result.output

            assert test_engine.search("Stale") == []
            assert len(test_engine.search("Findable")) == 1
            assert test_engine.search("Hidden") == []  # draft excluded
            assert len(test_engine.search("PR body")) == 1
