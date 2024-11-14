# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import pytest
from flask_sqlalchemy import SQLAlchemy

from app.models.auth import User
from app.models.organisation import Organisation
from app.services.reputation import update_reputations
from app.services.reputation._history import get_reputation_history
from app.services.social_graph import adapt

from ._compute import compute_reputation


def test_single_user(db: SQLAlchemy) -> None:
    joe = User(email="joe@example.com")
    db.session.add(joe)
    db.session.flush()

    score = compute_reputation(joe)["total"]
    assert score == 0


@pytest.mark.skip
def test_two_users(db: SQLAlchemy) -> None:
    joe = User(email="joe@example.com")
    jim = User(email="jim@example.com")
    db.session.add(joe)
    db.session.add(jim)
    db.session.flush()

    adapt(joe).follow(jim)
    db.session.flush()

    score = compute_reputation(joe)["total"]
    assert score == 0.1

    adapt(joe).unfollow(jim)
    db.session.flush()

    score = compute_reputation(joe)["total"]
    assert score == 0


def test_single_org(db: SQLAlchemy) -> None:
    joe = User(email="joe@example.com")
    org = Organisation(name="xxx")
    db.session.add(joe)
    db.session.add(org)
    db.session.flush()

    score = compute_reputation(org)["total"]
    assert score == 0


@pytest.mark.skip
def test_record(db: SQLAlchemy) -> None:
    joe = User(email="joe@example.com")
    jim = User(email="jim@example.com")
    db.session.add(joe)
    db.session.add(jim)
    db.session.flush()

    update_reputations()
    assert joe.karma == 0
    assert jim.karma == 0

    adapt(joe).follow(jim)
    db.session.flush()

    update_reputations()
    assert joe.karma == 0.1
    assert jim.karma == 0.1

    assert len(get_reputation_history(joe)) == 1
    assert len(get_reputation_history(jim)) == 1

    h = get_reputation_history(joe)[0]
    assert h.value == 0.1
    assert h.details["total"] == 0.1
