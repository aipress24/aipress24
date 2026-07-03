# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""End-to-end HTTP tests for the /api/v1 public API."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app.flask.main import create_app
from tests.conftest import TestConfig


def test_root_is_public(client: FlaskClient) -> None:
    response = client.get("/api/v1/")
    assert response.status_code == 200
    body = response.get_json()
    assert body["api"] == "AIpress24 API"
    assert body["_links"]["articles"]["href"] == "/api/v1/articles"
    assert body["_links"]["docs"]["href"] == "/api/v1/docs"


def test_openapi_document_is_served(client: FlaskClient) -> None:
    response = client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    spec = response.get_json()
    assert spec["openapi"].startswith("3.")
    assert "/api/v1/articles" in spec["paths"]


def test_missing_token_returns_json_401(
    client: FlaskClient, seed: SimpleNamespace
) -> None:
    response = client.get("/api/v1/articles")
    assert response.status_code == 401
    assert response.headers["Content-Type"].startswith("application/json")
    assert "WWW-Authenticate" in response.headers
    assert response.get_json()["code"] == 401


def test_invalid_token_returns_401(client: FlaskClient, seed: SimpleNamespace) -> None:
    response = client.get(
        "/api/v1/articles", headers={"Authorization": "Bearer a24_bogus"}
    )
    assert response.status_code == 401


def test_articles_list_only_published(
    client: FlaskClient, seed: SimpleNamespace, auth: dict
) -> None:
    response = client.get("/api/v1/articles", headers=auth)
    assert response.status_code == 200
    body = response.get_json()

    assert body["total"] == 3  # published only; draft + expired excluded
    titles = {item["title"] for item in body["items"]}
    assert titles == {"Public 1", "Public 2", "Long body"}

    item = body["items"][0]
    assert "owner_id" not in item  # PII redacted
    assert item["_links"]["self"]["href"].startswith("/api/v1/articles/")


def test_articles_pagination_next_link(
    client: FlaskClient, seed: SimpleNamespace, auth: dict
) -> None:
    response = client.get("/api/v1/articles?limit=1&offset=0", headers=auth)
    body = response.get_json()
    assert body["count"] == 1
    assert body["total"] == 3
    assert body["_links"]["next"]["href"] == "/api/v1/articles?limit=1&offset=1"


def test_article_detail_and_draft_404(
    client: FlaskClient, seed: SimpleNamespace, auth: dict
) -> None:
    ok = client.get(f"/api/v1/articles/{seed.published_1.id}", headers=auth)
    assert ok.status_code == 200
    assert ok.get_json()["id"] == seed.published_1.id

    hidden = client.get(f"/api/v1/articles/{seed.draft.id}", headers=auth)
    assert hidden.status_code == 404


def test_scope_is_enforced(client: FlaskClient, seed: SimpleNamespace) -> None:
    headers = {"Authorization": f"Bearer {seed.content_only_token}"}
    # read:content grants articles...
    assert client.get("/api/v1/articles", headers=headers).status_code == 200
    # ...but not the member directory.
    forbidden = client.get("/api/v1/members", headers=headers)
    assert forbidden.status_code == 403


def test_members_redact_contact_details(
    client: FlaskClient, seed: SimpleNamespace, auth: dict
) -> None:
    response = client.get("/api/v1/members", headers=auth)
    assert response.status_code == 200
    body = response.get_json()
    assert body["total"] >= 1
    member = body["items"][0]
    for leaked in ("email", "tel_mobile", "password", "fs_uniquifier", "is_clone"):
        assert leaked not in member


def test_organisations_list(
    client: FlaskClient, seed: SimpleNamespace, auth: dict
) -> None:
    response = client.get("/api/v1/organisations", headers=auth)
    assert response.status_code == 200
    assert response.get_json()["total"] >= 1


def test_events_list_only_published(
    client: FlaskClient, seed: SimpleNamespace, auth: dict
) -> None:
    response = client.get("/api/v1/events", headers=auth)
    assert response.status_code == 200
    body = response.get_json()
    assert body["total"] == 1  # the draft event is excluded
    assert body["items"][0]["title"] == "Expo"


def test_event_detail_and_draft_404(
    client: FlaskClient, seed: SimpleNamespace, auth: dict
) -> None:
    ok = client.get(f"/api/v1/events/{seed.event.id}", headers=auth)
    assert ok.status_code == 200
    hidden = client.get(f"/api/v1/events/{seed.draft_event.id}", headers=auth)
    assert hidden.status_code == 404


def test_unknown_api_path_returns_json_404(client: FlaskClient) -> None:
    # Routing-level 404 (no token needed): must be JSON, not the HTML page.
    response = client.get("/api/v1/nope-not-a-collection")
    assert response.status_code == 404
    assert response.headers["Content-Type"].startswith("application/json")
    assert response.get_json()["code"] == 404


def test_wrong_method_returns_json_405(client: FlaskClient) -> None:
    response = client.post("/api/v1/articles")
    assert response.status_code == 405
    assert response.headers["Content-Type"].startswith("application/json")


def test_non_api_404_stays_html(client: FlaskClient) -> None:
    # The HTML site must be unaffected by the API's error handling.
    response = client.get("/definitely-not-a-real-page")
    assert response.status_code == 404
    assert "text/html" in response.headers["Content-Type"]


def test_app_factory_is_reentrant() -> None:
    # register_on_app must not call setup methods on the shared blueprint, so a
    # second create_app() in the same process must not raise (regression).
    second = create_app(TestConfig)
    rules = {str(rule.rule) for rule in second.url_map.iter_rules()}
    assert "/api/v1/articles" in rules


def test_for_sale_article_body_gated_by_entitlement(
    client: FlaskClient,
    seed: SimpleNamespace,
    app: Flask,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A paywalled article's body must not leak to a non-entitled token."""
    full_body = seed.long_article.content
    url = f"/api/v1/articles/{seed.long_article.id}"
    author = {"Authorization": f"Bearer {seed.token}"}  # owns the article
    reader = {"Authorization": f"Bearer {seed.reader_token}"}  # not entitled

    # Paywall live: the non-entitled reader gets a truncated preview, not the body.
    monkeypatch.setitem(app.config, "STRIPE_LIVE_ENABLED", True)
    reader_body = client.get(url, headers=reader).get_json()["content"]
    assert reader_body != full_body
    assert len(reader_body) < len(full_body)

    # The author is entitled, so they still get the full body with the paywall live.
    assert client.get(url, headers=author).get_json()["content"] == full_body

    # Paywall off: parity with the UI, which shows the full body to everyone.
    monkeypatch.setitem(app.config, "STRIPE_LIVE_ENABLED", False)
    assert client.get(url, headers=reader).get_json()["content"] == full_body
