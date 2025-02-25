# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask_sqlalchemy import SQLAlchemy

from app.models.auth import User
from app.models.organisation import Organisation

from ...modules.wire.models import ArticlePost
from . import adapt


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
    article.newsroom_id = 42  # source Article.id
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
