# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask_sqlalchemy import SQLAlchemy

from app.models.auth import User
from app.models.content.textual import Article
from app.models.orgs import Organisation

from . import adapt


def test_followers_users(db: SQLAlchemy) -> None:
    _joe = User(email="joe@example.com")
    _jim = User(email="jim@example.com")
    db.session.add(_joe)
    db.session.add(_jim)
    db.session.flush()

    joe = adapt(_joe)
    jim = adapt(_jim)

    assert not joe.is_following(jim)
    assert not jim.is_following(joe)
    assert joe.num_followers() == 0
    assert joe.num_followees() == 0
    assert jim.num_followers() == 0
    assert jim.num_followees() == 0

    joe.follow(jim)
    db.session.flush()

    assert joe.is_following(jim)
    assert not joe.is_following(joe)
    assert joe.num_followers() == 0
    assert joe.num_followees() == 1
    assert jim.num_followers() == 1
    assert jim.num_followees() == 0

    assert len(jim.get_followers()) == 1
    assert len(jim.get_followees()) == 0
    assert len(joe.get_followers()) == 0
    assert len(joe.get_followees()) == 1

    joe.unfollow(jim)
    db.session.flush()

    assert not joe.is_following(jim)
    assert not jim.is_following(joe)
    assert joe.num_followers() == 0
    assert joe.num_followees() == 0
    assert jim.num_followers() == 0
    assert jim.num_followees() == 0


def test_followers_orgs(db: SQLAlchemy) -> None:
    _joe = User(email="joe@example.com")
    _org = Organisation(name="xxx", owner=_joe)
    db.session.add(_joe)
    db.session.add(_org)
    db.session.flush()

    joe = adapt(_joe)
    org = adapt(_org)

    assert not joe.is_following(org)
    assert org.num_followers() == 0
    assert joe.num_followees(cls=Organisation) == 0

    joe.follow(org)
    db.session.flush()

    assert joe.is_following(org)
    assert org.num_followers() == 1
    assert len(org.get_followers()) == 1
    assert joe.num_followees(cls=Organisation) == 1
    assert joe.num_followees(cls=User) == 0

    joe.unfollow(org)
    db.session.flush()

    assert not joe.is_following(org)
    assert org.num_followers() == 0
    assert joe.num_followees(cls=Organisation) == 0
    assert joe.num_followees(cls=User) == 0


def test_likes(db: SQLAlchemy) -> None:
    _joe = User(email="joe@example.com")
    _jim = User(email="jim@example.com")
    _article = Article(owner=_jim)
    db.session.add(_article)
    db.session.add(_joe)
    db.session.flush()

    joe = adapt(_joe)
    # jim = adapt(_jim)
    article = adapt(_article)

    assert article.num_likes() == 0

    joe.like(article)
    db.session.flush()

    assert article.num_likes() == 1

    joe.unlike(article)
    db.session.flush()

    assert article.num_likes() == 0
