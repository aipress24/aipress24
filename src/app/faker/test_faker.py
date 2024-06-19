# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import pytest
from flask.app import Flask
from flask.testing import FlaskClient
from flask_sqlalchemy import SQLAlchemy
from flask_super.registry import lookup

from app.faker import FakerService
from app.services.roles import Role, has_role

from ._faker import FAKER_TEST_SETTINGS
from ._scripts.base import FakerScript


@pytest.mark.skip(reason="Need to set up taxonomies first.")
def test_faker(db: SQLAlchemy, client: FlaskClient) -> None:
    faker = FakerService(db, settings=FAKER_TEST_SETTINGS)
    faker.generate_fake_entities()

    repository = faker.repository
    users = repository["users"]
    events = repository["events"]
    articles = repository["articles"]

    assert len(users) > 0
    assert len(events) > 0
    assert len(articles) > 0

    article = articles[0]
    assert article.published_at is not None

    user0 = users[0]
    assert has_role(user0, Role.PRESS_MEDIA)

    # FIXME
    # user1 = users[1]
    # assert has_role(user1, Role.PRESS_RELATIONS)
    #
    # user2 = users[2]
    # assert has_role(user2, Role.EXPERT)
    #
    # user3 = users[3]
    # assert has_role(user3, Role.TRANSFORMER)
    #
    # user4 = users[4]
    # assert has_role(user4, Role.ACADEMIC)


def test_script_lookup(app: Flask) -> None:
    scripts = lookup(FakerScript)
    assert len(scripts) > 0
