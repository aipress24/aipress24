# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for api/likes.py."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flask import g

from app.models.auth import User
from app.modules.api.likes import toggle_like
from app.modules.swork.models import ShortPost
from app.services.social_graph import adapt

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


@pytest.fixture
def post_owner(db_session: Session) -> User:
    """Create a post owner."""
    user = User(email="owner@example.com", first_name="Post", last_name="Owner")
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def liker_user(db_session: Session) -> User:
    """Create a user who likes posts."""
    user = User(email="liker@example.com", first_name="Post", last_name="Liker")
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def short_post(db_session: Session, post_owner: User) -> ShortPost:
    """Create a short post for testing."""
    post = ShortPost(owner=post_owner, content="Test post content")
    db_session.add(post)
    db_session.flush()
    return post


class TestToggleLike:
    """Tests for toggle_like function."""

    def test_toggle_like_adds_like(
        self, app: Flask, db_session: Session, short_post: ShortPost, liker_user: User
    ):
        """Test that toggle_like adds a like when user hasn't liked."""
        with app.test_request_context():
            g.user = liker_user

            # Initially no likes
            assert short_post.like_count == 0

            result = toggle_like(short_post)

            # Like count should be updated
            assert short_post.like_count == 1
            assert result == "1"

    def test_toggle_like_removes_like(
        self, app: Flask, db_session: Session, short_post: ShortPost, liker_user: User
    ):
        """Test that toggle_like removes like when user already liked."""
        # First add a like
        social_user = adapt(liker_user)
        social_user.like(short_post)
        db_session.flush()
        short_post.like_count = adapt(short_post).num_likes()
        db_session.flush()

        with app.test_request_context():
            g.user = liker_user

            assert short_post.like_count == 1

            result = toggle_like(short_post)

            assert short_post.like_count == 0
            assert result == "0"

    def test_toggle_like_returns_count_string(
        self, app: Flask, db_session: Session, short_post: ShortPost, liker_user: User
    ):
        """Test that toggle_like returns a string count."""
        with app.test_request_context():
            g.user = liker_user

            result = toggle_like(short_post)

            assert isinstance(result, str)

    def test_toggle_like_multiple_times(
        self, app: Flask, db_session: Session, short_post: ShortPost, liker_user: User
    ):
        """Test toggling like multiple times."""
        with app.test_request_context():
            g.user = liker_user

            # Toggle on
            toggle_like(short_post)
            assert short_post.like_count == 1

            # Toggle off
            toggle_like(short_post)
            assert short_post.like_count == 0

            # Toggle on again
            toggle_like(short_post)
            assert short_post.like_count == 1
