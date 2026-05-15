# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for wire/views/item.py metadata list builder.

Locks in the geoloc rendering on the article/press-release detail pages
(ticket #0021): Pays / Ville entries appear when fields are populated and
disappear when they are not.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.models.auth import User
from app.modules.wire.models import ArticlePost, PressReleasePost
from app.modules.wire.views.item import ArticleVM, ItemDetailView, PressReleaseVM

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


@pytest.fixture
def post_owner(db_session: Session) -> User:
    user = User(
        email="wire_meta_owner@example.com", first_name="Wire", last_name="Meta"
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def article_with_geoloc(db_session: Session, post_owner: User) -> ArticlePost:
    post = ArticlePost(
        owner=post_owner,
        title="Article Geo",
        content="...",
        summary="",
        genre="actu",
        sector="tech",
        topic="news",
        section="rubrique",
        address="10 rue du test",
        pays_zip_ville="FRA",
        pays_zip_ville_detail="FRA / 75001 Paris",
    )
    db_session.add(post)
    db_session.flush()
    return post


@pytest.fixture
def press_release_with_geoloc(
    db_session: Session, post_owner: User
) -> PressReleasePost:
    post = PressReleasePost(
        owner=post_owner,
        title="Communiqué Geo",
        content="...",
        summary="",
        genre="presse",
        sector="tech",
        topic="news",
        section="rubrique",
        pays_zip_ville="ESP",
        pays_zip_ville_detail="ESP / 28001 Madrid",
    )
    db_session.add(post)
    db_session.flush()
    return post


class TestOrglessAuthorDoesNotCrash:
    """Regression (audit 2026-05-15, C1): an article/press-release
    whose author has no organisation must render.

    `UserVM.get_organisation()` in `wire/views/item.py` ended with a
    bare `assert result`. `Wrapper.__attrs_post_init__` calls
    `extra_attrs()` eagerly at construction, and `PostMixin` builds
    `UserVM(post.owner)` for every article / press-release render — so
    any author with `organisation_id = None` raised `AssertionError`
    and 500'd the detail page. Same root cause as the events
    orgless-participant crash (lessons-learned #3); the safe twin in
    `common/components/post_card.py` already returns None.
    """

    def test_article_vm_builds_with_orgless_author(
        self, app: Flask, db_session: Session, post_owner: User
    ) -> None:
        assert post_owner.organisation is None  # fixture has no org
        post = ArticlePost(
            owner=post_owner,
            title="Orgless author article",
            content="...",
            summary="",
            genre="actu",
            sector="tech",
            topic="news",
            section="rubrique",
        )
        db_session.add(post)
        db_session.flush()

        with app.test_request_context():
            # Eager extra_attrs() → UserVM(post.owner) → get_organisation()
            vm = ArticleVM(post)
            assert vm.author.organisation is None

    def test_press_release_vm_builds_with_orgless_author(
        self, app: Flask, db_session: Session, post_owner: User
    ) -> None:
        post = PressReleasePost(
            owner=post_owner,
            title="Orgless author PR",
            content="...",
            summary="",
            genre="actu",
            sector="tech",
            topic="news",
            section="rubrique",
        )
        db_session.add(post)
        db_session.flush()

        with app.test_request_context():
            vm = PressReleaseVM(post)
            assert vm.author.organisation is None


class TestArticleMetadata:
    def test_country_label_present_when_pays_set(
        self, app: Flask, db_session: Session, article_with_geoloc: ArticlePost
    ) -> None:
        view = ItemDetailView()
        with app.test_request_context():
            metadata = view._get_metadata_list(article_with_geoloc)
            labels = [m["label"] for m in metadata]
            assert "Pays" in labels

    def test_city_label_present_when_detail_set(
        self, app: Flask, db_session: Session, article_with_geoloc: ArticlePost
    ) -> None:
        view = ItemDetailView()
        with app.test_request_context():
            metadata = view._get_metadata_list(article_with_geoloc)
            labels = [m["label"] for m in metadata]
            assert "Ville" in labels

    def test_address_label_present_when_address_set(
        self, app: Flask, db_session: Session, article_with_geoloc: ArticlePost
    ) -> None:
        view = ItemDetailView()
        with app.test_request_context():
            metadata = view._get_metadata_list(article_with_geoloc)
            labels = [m["label"] for m in metadata]
            assert "Adresse" in labels

    def test_geoloc_omitted_when_unset(
        self, app: Flask, db_session: Session, post_owner: User
    ) -> None:
        post = ArticlePost(
            owner=post_owner,
            title="Article sans géo",
            content="x",
            summary="",
            genre="g",
            sector="s",
            topic="t",
            section="r",
        )
        db_session.add(post)
        db_session.flush()

        view = ItemDetailView()
        with app.test_request_context():
            metadata = view._get_metadata_list(post)
            labels = [m["label"] for m in metadata]
            assert "Pays" not in labels
            assert "Ville" not in labels
            assert "Adresse" not in labels


class TestPressReleaseMetadata:
    def test_country_label_present_when_pays_set(
        self,
        app: Flask,
        db_session: Session,
        press_release_with_geoloc: PressReleasePost,
    ) -> None:
        view = ItemDetailView()
        with app.test_request_context():
            metadata = view._get_metadata_list(press_release_with_geoloc)
            labels = [m["label"] for m in metadata]
            assert "Pays" in labels
            assert "Ville" in labels
