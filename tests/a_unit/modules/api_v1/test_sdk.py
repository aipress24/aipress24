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
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
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
        self.calls: list[dict] = []

    def _open(
        self,
        url: str,
        headers: dict,
        method: str = "GET",
        data: bytes | None = None,
    ) -> tuple[int, bytes]:
        self.calls.append(
            {"url": url, "headers": headers, "method": method, "data": data}
        )
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
    assert client.calls[0]["headers"]["Authorization"] == "Bearer a24_secret"


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


def test_create_posts_json_body() -> None:
    url = "https://ex.test/api/v1/me/press-releases"
    client = StubClient({url: (201, {"id": 7, "titre": "Hi", "status": "draft"})})
    result = client.create("me/press-releases", {"titre": "Hi"})
    assert result["id"] == 7
    call = client.calls[0]
    assert call["method"] == "POST"
    assert json.loads(call["data"]) == {"titre": "Hi"}
    assert call["headers"]["Content-Type"] == "application/json"


def test_publish_and_delete_use_the_right_verbs() -> None:
    pub = "https://ex.test/api/v1/me/press-releases/7/publish"
    dele = "https://ex.test/api/v1/me/press-releases/7"
    client = StubClient({pub: (200, {"id": 7, "status": "public"}), dele: (204, {})})
    assert client.publish("me/press-releases", 7)["status"] == "public"
    client.delete("me/press-releases", 7)
    methods = {call["url"]: call["method"] for call in client.calls}
    assert methods[pub] == "POST"
    assert methods[dele] == "DELETE"


def test_me_targets_the_self_endpoint() -> None:
    url = "https://ex.test/api/v1/me"
    client = StubClient({url: (200, {"id": 1, "email": "me@example.com"})})
    assert client.me()["email"] == "me@example.com"
    assert client.calls[0]["method"] == "GET"


@pytest.mark.parametrize(
    "href",
    [
        "https://evil.test/api/v1/articles",
        "http://ex.test/api/v1/articles",
        "https://ex.test:8443/api/v1/articles",
        "https://ex.test@evil.test/api/v1/articles",
        "HTTPS://evil.test/api/v1/articles",
    ],
)
def test_the_token_never_leaves_the_configured_origin(href: str) -> None:
    client = StubClient({})
    with pytest.raises(ValueError, match="origin"):
        client._request(href)
    assert client.calls == []


def test_an_absolute_link_to_the_configured_origin_is_followed() -> None:
    url = "https://ex.test/api/v1/articles?limit=1"
    assert StubClient({url: (200, {"total": 3})})._request(url) == {"total": 3}


def test_redirects_are_not_followed_with_the_token() -> None:
    seen: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            seen.append(self.path)
            self.send_response(302)
            self.send_header("Location", "/elsewhere")
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        client = Client("a24_x", base_url=f"http://127.0.0.1:{server.server_port}")
        with pytest.raises(ApiError) as excinfo:
            client.me()
    finally:
        server.shutdown()
        server.server_close()

    assert excinfo.value.status == 302
    assert seen == ["/api/v1/me"]


def test_a_hostile_filename_cannot_add_multipart_headers() -> None:
    url = "https://ex.test/api/v1/me/press-releases/7/images"
    client = StubClient({url: (201, {"id": 1})})

    client.add_press_release_image(7, b"bytes", 'a"\r\nX-Evil: 1.png')

    body = client.calls[0]["data"]
    assert b'filename="a%22%0D%0AX-Evil: 1.png"' in body
    assert b"\r\nX-Evil" not in body


@pytest.mark.parametrize("base_url", ["", "file:///etc", "ftp://ex.test", "ex.test"])
def test_base_url_must_be_http(base_url: str) -> None:
    with pytest.raises(ValueError, match="base_url"):
        Client("a24_x", base_url=base_url)
