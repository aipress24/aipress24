# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for unauthenticated web access.

These tests verify that unauthenticated users are properly redirected to login
for protected routes, and that public routes are accessible.
"""

from __future__ import annotations

import time
import typing

from flask_sqlalchemy import SQLAlchemy

from app.flask.routing import url_for

if typing.TYPE_CHECKING:
    from flask.app import Flask
    from werkzeug.routing import Rule


def test_home(app: Flask, fresh_db: SQLAlchemy) -> None:
    """Test that home page redirects unauthenticated users."""
    client = app.test_client()
    res = client.get(url_for("public.home"))
    assert res.status_code == 302


def test_wire(app: Flask, fresh_db: SQLAlchemy) -> None:
    """Test wire routes redirect for unauthenticated users."""
    client = app.test_client()

    res = client.get(url_for("wire.wire"))
    assert res.status_code == 302


def test_members(app: Flask, fresh_db: SQLAlchemy) -> None:
    """Test member routes for unauthenticated users.

    Note: Some routes may return 200 for public pages.
    """
    client = app.test_client()

    # Profile redirects to login
    res = client.get(url_for("swork.profile"))
    assert res.status_code == 302


def test_events(app: Flask, fresh_db: SQLAlchemy) -> None:
    """Test event routes for unauthenticated users."""
    client = app.test_client()

    res = client.get(url_for("events.events"))
    # Events may be publicly viewable or redirect
    assert res.status_code in {200, 302}


def test_wip(app: Flask, fresh_db: SQLAlchemy) -> None:
    """Test WIP routes redirect for unauthenticated users."""
    client = app.test_client()

    res = client.get(url_for("wip.wip"))
    assert res.status_code == 302

    res = client.get(url_for("wip.dashboard"))
    assert res.status_code == 302


def test_all_unparameterized_endpoints(app: Flask, fresh_db: SQLAlchemy) -> None:
    """Test that all endpoints return 200 or 302 for unauthenticated users."""
    client = app.test_client()

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
        # Skip search - requires Typesense configuration
        "/search/",
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
