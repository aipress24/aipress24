# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask_sqlalchemy import SQLAlchemy

from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.wire.models import ArticlePost
from app.services.social_graph import adapt


def test_followers_users(db: SQLAlchemy) -> None:
    joe = User(email="joe@example.com")
    jim = User(email="jim@example.com")
    db.session.add(joe)
    db.session.add(jim)
    db.session.flush()

    social_joe = adapt(joe)
    social_jim = adapt(jim)

    assert not social_joe.is_following(social_jim)
    assert not social_jim.is_following(social_joe)
    assert social_joe.num_followers() == 0
    assert social_joe.num_followees() == 0
    assert social_jim.num_followers() == 0
    assert social_jim.num_followees() == 0

    social_joe.follow(social_jim)
    db.session.flush()

    assert social_joe.is_following(social_jim)
    assert not social_joe.is_following(social_joe)
    assert social_joe.num_followers() == 0
    assert social_joe.num_followees() == 1
    assert social_jim.num_followers() == 1
    assert social_jim.num_followees() == 0

    assert len(social_jim.get_followers()) == 1
    assert len(social_jim.get_followees()) == 0
    assert len(social_joe.get_followers()) == 0
    assert len(social_joe.get_followees()) == 1

    social_joe.unfollow(social_jim)
    db.session.flush()

    assert not social_joe.is_following(social_jim)
    assert not social_jim.is_following(social_joe)
    assert social_joe.num_followers() == 0
    assert social_joe.num_followees() == 0
    assert social_jim.num_followers() == 0
    assert social_jim.num_followees() == 0


def test_followers_orgs(db: SQLAlchemy) -> None:
    joe = User(email="joe@example.com")
    org = Organisation(name="xxx")
    db.session.add(joe)
    db.session.add(org)
    db.session.flush()

    social_joe = adapt(joe)
    social_org = adapt(org)

    assert not social_joe.is_following(social_org)
    assert social_org.num_followers() == 0
    assert social_joe.num_followees(cls=Organisation) == 0

    social_joe.follow(social_org)
    db.session.flush()

    assert social_joe.is_following(social_org)
    assert social_org.num_followers() == 1
    assert len(social_org.get_followers()) == 1
    assert social_joe.num_followees(cls=Organisation) == 1
    assert social_joe.num_followees(cls=User) == 0

    social_joe.unfollow(social_org)
    db.session.flush()

    assert not social_joe.is_following(social_org)
    assert social_org.num_followers() == 0
    assert social_joe.num_followees(cls=Organisation) == 0
    assert social_joe.num_followees(cls=User) == 0


def test_likes(db: SQLAlchemy) -> None:
    joe = User(email="joe@example.com")
    article = ArticlePost(owner=joe)
    # article.newsroom_id = 42  # source Article.id
    db.session.add(article)
    db.session.add(joe)
    db.session.flush()

    social_joe = adapt(joe)
    # jim = adapt(_jim)
    social_article = adapt(article)

    assert social_article.num_likes() == 0

    social_joe.like(social_article)
    db.session.flush()

    assert social_article.num_likes() == 1

    social_joe.unlike(social_article)
    db.session.flush()

    assert social_article.num_likes() == 0


def test_follow_self_raises_error(db: SQLAlchemy) -> None:
    """Test that following yourself with raw User raises SocialGraphError."""
    import pytest

    from app.services.social_graph._adapters import SocialGraphError

    joe = User(email="joe@example.com")
    db.session.add(joe)
    db.session.flush()

    social_joe = adapt(joe)

    # Following yourself with a raw User object raises error
    with pytest.raises(SocialGraphError, match="can't follow themself"):
        social_joe.follow(joe)


def test_get_followers_with_order_and_limit(db: SQLAlchemy) -> None:
    """Test get_followers with order_by and limit parameters."""
    joe = User(email="joe@example.com")
    jim = User(email="jim@example.com")
    jane = User(email="jane@example.com")
    db.session.add_all([joe, jim, jane])
    db.session.flush()

    social_joe = adapt(joe)
    social_jim = adapt(jim)
    social_jane = adapt(jane)

    # Have jim and jane follow joe
    social_jim.follow(joe)
    social_jane.follow(joe)
    db.session.flush()

    # Test with limit
    followers = social_joe.get_followers(limit=1)
    assert len(followers) == 1

    # Test with order_by
    followers = social_joe.get_followers(order_by=User.email)
    assert len(followers) == 2
    # Should be ordered by email
    assert followers[0].email == "jane@example.com"
    assert followers[1].email == "jim@example.com"


def test_get_followees_with_order_and_limit(db: SQLAlchemy) -> None:
    """Test get_followees with order_by and limit parameters."""
    joe = User(email="joe@example.com")
    jim = User(email="jim@example.com")
    jane = User(email="jane@example.com")
    db.session.add_all([joe, jim, jane])
    db.session.flush()

    social_joe = adapt(joe)

    # Have joe follow jim and jane
    social_joe.follow(jim)
    social_joe.follow(jane)
    db.session.flush()

    # Test with limit
    followees = social_joe.get_followees(limit=1)
    assert len(followees) == 1

    # Test with order_by
    followees = social_joe.get_followees(order_by=User.email)
    assert len(followees) == 2
    assert followees[0].email == "jane@example.com"
    assert followees[1].email == "jim@example.com"


def test_get_followees_organisations_with_limit(db: SQLAlchemy) -> None:
    """Test get_followees for organisations with limit."""
    joe = User(email="joe@example.com")
    org1 = Organisation(name="Org A")
    org2 = Organisation(name="Org B")
    db.session.add_all([joe, org1, org2])
    db.session.flush()

    social_joe = adapt(joe)

    social_joe.follow(org1)
    social_joe.follow(org2)
    db.session.flush()

    # Test with limit
    followees = social_joe.get_followees(cls=Organisation, limit=1)
    assert len(followees) == 1

    # Test with order_by
    followees = social_joe.get_followees(cls=Organisation, order_by=Organisation.name)
    assert len(followees) == 2
    assert followees[0].name == "Org A"
    assert followees[1].name == "Org B"


def test_is_following_with_raw_user_and_org(db: SQLAlchemy) -> None:
    """Test is_following with raw User and Organisation objects."""
    joe = User(email="joe@example.com")
    jim = User(email="jim@example.com")
    org = Organisation(name="Test Org")
    db.session.add_all([joe, jim, org])
    db.session.flush()

    social_joe = adapt(joe)

    # Follow using raw objects (not adapted)
    social_joe.follow(jim)
    social_joe.follow(org)
    db.session.flush()

    # Check is_following with raw objects
    assert social_joe.is_following(jim)
    assert social_joe.is_following(org)


def test_like_when_already_liking(db: SQLAlchemy) -> None:
    """Test that calling like() when already liking is idempotent."""
    joe = User(email="joe@example.com")
    article = ArticlePost(owner=joe)
    db.session.add_all([joe, article])
    db.session.flush()

    social_joe = adapt(joe)
    social_article = adapt(article)

    # Like the article
    social_joe.like(social_article)
    db.session.flush()
    assert social_article.num_likes() == 1

    # Like again - should be idempotent (early return)
    social_joe.like(social_article)
    db.session.flush()
    assert social_article.num_likes() == 1


def test_unlike_when_not_liking(db: SQLAlchemy) -> None:
    """Test that calling unlike() when not liking is safe."""
    joe = User(email="joe@example.com")
    article = ArticlePost(owner=joe)
    db.session.add_all([joe, article])
    db.session.flush()

    social_joe = adapt(joe)
    social_article = adapt(article)

    # Unlike when not liking - should be safe (early return)
    social_joe.unlike(social_article)
    db.session.flush()
    assert social_article.num_likes() == 0


def test_adapt_unsupported_type(db: SQLAlchemy) -> None:
    """Test that adapt raises NotImplementedError for unsupported types."""
    import pytest

    # Try to adapt an unsupported type
    with pytest.raises(NotImplementedError, match="Adaptation of.*not implemented"):
        adapt("unsupported")
