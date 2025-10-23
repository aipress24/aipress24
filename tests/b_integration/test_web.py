# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import typing

from app.flask.routing import url_for
from app.models.auth import User
from app.modules.wire.models import ArticlePost

if typing.TYPE_CHECKING:
    from flask.app import Flask
    from flask.testing import FlaskClient
    from flask_sqlalchemy import SQLAlchemy
    from werkzeug.routing import Rule


def test_home(client: FlaskClient) -> None:
    res = client.get(url_for("public.home"))
    assert res.status_code == 302


def test_wire(db: SQLAlchemy, client: FlaskClient) -> None:
    stuff = _create_stuff(db)

    res = client.get(url_for("wire.wire"))
    assert res.status_code == 302

    res = client.get(url_for("wire.wire", current_tab="wires"))
    assert res.status_code == 302

    res = client.get(url_for("wire.item", id=stuff["article"].id))
    assert res.status_code == 302


def test_members(db: SQLAlchemy, client: FlaskClient) -> None:
    ctx = _create_stuff(db)

    res = client.get(url_for("swork.members"))
    assert res.status_code == 302

    res = client.get(url_for("swork.profile"))
    assert res.status_code == 302

    url = url_for("swork.member", id=ctx["user"].id)
    res = client.get(url)
    assert res.status_code == 302


def test_events(db: SQLAlchemy, client: FlaskClient) -> None:
    _create_stuff(db)

    res = client.get(url_for("events.events"))
    assert res.status_code == 302

    res = client.get(url_for("events.events", current_tab="all"))
    assert res.status_code == 302


# def test_search(db: SQLAlchemy, client):
#     _create_stuff(db)
#     res = client.get(url_for("private.search"))
#     assert res.status_code == 200


def test_wip(db: SQLAlchemy, client: FlaskClient) -> None:
    _create_stuff(db)
    res = client.get(url_for("wip.wip"))
    assert res.status_code == 302

    res = client.get(url_for("wip.dashboard"))
    assert res.status_code == 302

    res = client.get("/wip/contents?mode=list")
    assert res.status_code == 302

    res = client.get("/wip/contents?mode=create&doc_type=press-release")
    assert res.status_code == 302


def test_all_unparameterized_endpoints(
    app: Flask, db: SQLAlchemy, client: FlaskClient
) -> None:
    _create_stuff(db)

    ignore_prefixes = ["/_", "/admin/", "/static/", "/auth/"]

    rules: list[Rule] = list(app.url_map.iter_rules())
    for rule in rules:
        if any(rule.rule.startswith(p) for p in ignore_prefixes):
            continue

        if "<" in rule.rule:
            continue

        res = client.get(rule.rule)
        assert res.status_code in {302, 200}, f"Request failed on {rule.rule}"


def _create_stuff(db: SQLAlchemy) -> dict[str, User | ArticlePost]:
    owner = User(email="joe@example.com", id=0)
    db.session.add(owner)
    article = ArticlePost(owner=owner)
    db.session.add(article)
    db.session.flush()

    return {
        "user": owner,
        "article": article,
    }
