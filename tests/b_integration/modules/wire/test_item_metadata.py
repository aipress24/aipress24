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
from app.modules.wire.views.item import ItemDetailView

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


@pytest.fixture
def post_owner(db_session: Session) -> User:
    user = User(email="wire_meta_owner@example.com", first_name="Wire", last_name="Meta")
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
