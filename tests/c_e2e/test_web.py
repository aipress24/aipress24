# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import time
import typing

from app.enums import RoleEnum
from app.flask.routing import url_for
from app.models.auth import Role, User
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

    # Note: /wip/contents doesn't exist, use specific content types
    # res = client.get("/wip/contents?mode=list")
    # assert res.status_code == 302

    # res = client.get("/wip/contents?mode=create&doc_type=press-release")
    # assert res.status_code == 302


def test_all_unparameterized_endpoints(
    app: Flask, db: SQLAlchemy, client: FlaskClient
) -> None:
    _create_stuff(db)

    ignore_prefixes = [
        "/_",
        "/admin/",
        "/static/",
        "/auth/",
        "/debug/",
        "/kyc/",
        "/preferences/",
        "/webhook",
        "/system/boot",
    ]
    # Skip endpoints that are internal helpers or not meant to be called directly
    skip_endpoints = ["update_breadcrumbs"]

    rules: list[Rule] = list(app.url_map.iter_rules())
    for rule in rules:
        if any(rule.rule.startswith(p) for p in ignore_prefixes):
            continue

        # Skip internal/helper endpoints
        if any(skip in rule.endpoint for skip in skip_endpoints):
            continue

        if "<" in rule.rule:
            continue

        # Skip routes that don't accept GET
        if not rule.methods or "GET" not in rule.methods:
            continue

        t0 = time.time()
        print("Checking route:", rule.rule)
        res = client.get(rule.rule)
        print("  -> status code:", res.status_code, f"(in {time.time() - t0:.2f}s)")

        assert res.status_code in {302, 200}, f"Request failed on {rule.rule}"


def _create_stuff(db: SQLAlchemy) -> dict[str, User | ArticlePost]:
    # Create or get the PRESS_MEDIA role
    role = db.session.query(Role).filter_by(name=RoleEnum.PRESS_MEDIA.name).first()
    if not role:
        role = Role(
            name=RoleEnum.PRESS_MEDIA.name, description=RoleEnum.PRESS_MEDIA.value
        )
        db.session.add(role)
        db.session.flush()

    # Check if test user already exists (from previous E2E test)
    # Check both by email and by id since either could cause uniqueness issues
    owner = db.session.query(User).filter_by(email="joe@example.com").first()
    if not owner:
        owner = db.session.query(User).filter_by(id=0).first()
    if not owner:
        owner = User(email="joe@example.com", id=0)
        # Set minimal photo to avoid errors in template rendering
        owner.photo = b""  # Empty bytes to avoid None errors
        owner.roles.append(role)
        db.session.add(owner)
        db.session.flush()

    # Check if test article already exists
    article = db.session.query(ArticlePost).filter_by(owner_id=owner.id).first()
    if not article:
        article = ArticlePost(owner=owner)
        db.session.add(article)
        db.session.flush()

    return {
        "user": owner,
        "article": article,
    }
