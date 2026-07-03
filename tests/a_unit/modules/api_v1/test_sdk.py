# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""Unit tests for the standalone Python SDK (sdk/python/aipress24_client).

The HTTP layer (``_open``) is stubbed, so these exercise URL building,
the bearer header, ``next``-link pagination and error handling without a
network or a running server.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SDK_PATH = Path(__file__).resolve().parents[4] / "sdk" / "python"
if str(SDK_PATH) not in sys.path:
    sys.path.insert(0, str(SDK_PATH))

from aipress24_client import ApiError, Client  # noqa: E402


class StubClient(Client):
    """A Client whose HTTP layer returns canned JSON responses by URL."""

    def __init__(self, responses: dict) -> None:
        super().__init__(token="a24_secret", base_url="https://ex.test")
        self.responses = responses
        self.calls: list[tuple[str, dict]] = []

    def _open(self, url: str, headers: dict) -> tuple[int, bytes]:
        self.calls.append((url, headers))
        status, body = self.responses[url]
        return status, json.dumps(body).encode()


def test_url_building() -> None:
    client = Client("a24_x", base_url="https://ex.test/")
    assert (
        client._url("articles", {"limit": 10, "offset": 0})
        == "https://ex.test/api/v1/articles?limit=10&offset=0"
    )
    # Absolute paths (as returned in _links) are used as-is under the base URL.
    assert (
        client._url("/api/v1/articles?limit=1&offset=1")
        == "https://ex.test/api/v1/articles?limit=1&offset=1"
    )
    # None-valued params are dropped.
    assert client._url("articles", {"limit": None}) == "https://ex.test/api/v1/articles"


def test_list_sends_bearer_header() -> None:
    url = "https://ex.test/api/v1/articles?limit=20&offset=0"
    client = StubClient(
        {url: (200, {"items": [{"id": 1}], "total": 1, "limit": 20, "offset": 0})}
    )
    page = client.articles()
    assert [item["id"] for item in page] == [1]
    assert page.total == 1
    assert client.calls[0][1]["Authorization"] == "Bearer a24_secret"


def test_iter_follows_next_links() -> None:
    url1 = "https://ex.test/api/v1/articles?limit=1&offset=0"
    url2 = "https://ex.test/api/v1/articles?limit=1&offset=1"
    client = StubClient(
        {
            url1: (
                200,
                {
                    "items": [{"id": 1}],
                    "total": 2,
                    "limit": 1,
                    "offset": 0,
                    "_links": {"next": {"href": "/api/v1/articles?limit=1&offset=1"}},
                },
            ),
            url2: (
                200,
                {
                    "items": [{"id": 2}],
                    "total": 2,
                    "limit": 1,
                    "offset": 1,
                    "_links": {},
                },
            ),
        }
    )
    assert [item["id"] for item in client.iter("articles", limit=1)] == [1, 2]


def test_error_response_raises_api_error() -> None:
    url = "https://ex.test/api/v1/members?limit=20&offset=0"
    client = StubClient(
        {url: (403, {"code": 403, "status": "Forbidden", "message": "no scope"})}
    )
    with pytest.raises(ApiError) as excinfo:
        client.members()
    assert excinfo.value.status == 403
    assert excinfo.value.payload["message"] == "no scope"
