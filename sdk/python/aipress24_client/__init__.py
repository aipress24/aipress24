# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""A tiny, dependency-free Python client for the AIpress24 public API.

Uses only the standard library (``urllib``), so it can be vendored or
``pip install``-ed with no transitive dependencies.

    from aipress24_client import Client

    api = Client(token="a24_…", base_url="https://aipress24.com")
    for article in api.iter("articles"):
        print(article["title"], article["_links"]["self"]["href"])

Every resource is exposed generically via :meth:`Client.list`,
:meth:`Client.get_one` and :meth:`Client.iter`, plus named convenience
methods (``articles``, ``events``, ``members``, …).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterator
from typing import Any

# COLLECTIONS and the per-resource TypedDict models are generated from the
# OpenAPI spec (see ../generate.py); a unit test keeps them in sync.
from ._generated import COLLECTIONS

__all__ = ["COLLECTIONS", "ApiError", "Client", "Page"]

__version__ = "0.1.0"

DEFAULT_BASE_URL = "https://aipress24.com"
API_PREFIX = "/api/v1"


class ApiError(Exception):
    """Raised for any non-2xx API response."""

    def __init__(self, status: int, payload: dict[str, Any] | None) -> None:
        self.status = status
        self.payload = payload or {}
        message = self.payload.get("message") or self.payload.get("status") or "error"
        super().__init__(f"HTTP {status}: {message}")


class Page:
    """One page of a collection, with helpers to walk to the next page."""

    def __init__(self, client: Client, body: dict[str, Any]) -> None:
        self._client = client
        self.items: list[dict[str, Any]] = body.get("items", [])
        self.total: int = body.get("total", len(self.items))
        self.limit: int = body.get("limit", len(self.items))
        self.offset: int = body.get("offset", 0)
        self.links: dict[str, dict[str, str]] = body.get("_links", {})

    @property
    def has_next(self) -> bool:
        return "next" in self.links

    def next_page(self) -> Page | None:
        href = self.links.get("next", {}).get("href")
        if not href:
            return None
        return Page(self._client, self._client._request(href))

    def __iter__(self) -> Iterator[dict[str, Any]]:
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)


class Client:
    """A client for the AIpress24 public API (``/api/v1``).

    Reads are available to any valid token (subject to its scopes); the
    owner-scoped ``/me`` reads need ``read:self`` and the authoring/publishing
    writes need ``write:content``.
    """

    def __init__(
        self,
        token: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
    ) -> None:
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # --- low-level HTTP (override _open in tests) -------------------------

    def _open(
        self,
        url: str,
        headers: dict[str, str],
        method: str = "GET",
        data: bytes | None = None,
    ) -> tuple[int, bytes]:
        request = urllib.request.Request(  # noqa: S310
            url, headers=headers, method=method, data=data
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:  # noqa: S310
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.read()

    def _url(self, path: str, params: dict[str, Any] | None = None) -> str:
        if path.startswith(("http://", "https://")):
            url = path
        elif path.startswith("/"):
            url = self.base_url + path
        else:
            url = f"{self.base_url}{API_PREFIX}/{path}"
        if params:
            clean = {k: v for k, v in params.items() if v is not None}
            if clean:
                sep = "&" if "?" in url else "?"
                url = url + sep + urllib.parse.urlencode(clean)
        return url

    def _request(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        method: str = "GET",
        json_body: dict[str, Any] | None = None,
    ) -> dict:
        url = self._url(path, params)
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }
        data: bytes | None = None
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        status, raw = self._open(url, headers, method=method, data=data)
        try:
            body = json.loads(raw) if raw else {}
        except ValueError:
            body = {}
        if not 200 <= status < 300:
            raise ApiError(status, body)
        return body

    # --- generic resource access -----------------------------------------

    def root(self) -> dict:
        """Fetch the API discovery document (link relations, docs URLs)."""
        return self._request(f"{API_PREFIX}/")

    def list(self, collection: str, limit: int = 20, offset: int = 0) -> Page:
        """Fetch one page of a collection."""
        return Page(self, self._request(collection, {"limit": limit, "offset": offset}))

    def get_one(self, collection: str, identifier: Any) -> dict:
        """Fetch a single resource by id."""
        return self._request(f"{collection}/{identifier}")

    def iter(self, collection: str, limit: int = 50) -> Iterator[dict[str, Any]]:
        """Iterate over every item in a collection, following ``next`` links."""
        page: Page | None = self.list(collection, limit=limit, offset=0)
        while page is not None:
            yield from page.items
            page = page.next_page()

    # --- named convenience methods ---------------------------------------

    def articles(self, limit: int = 20, offset: int = 0) -> Page:
        return self.list("articles", limit, offset)

    def article(self, identifier: int) -> dict:
        return self.get_one("articles", identifier)

    def press_releases(self, limit: int = 20, offset: int = 0) -> Page:
        return self.list("press-releases", limit, offset)

    def press_release(self, identifier: int) -> dict:
        return self.get_one("press-releases", identifier)

    def events(self, limit: int = 20, offset: int = 0) -> Page:
        return self.list("events", limit, offset)

    def event(self, identifier: int) -> dict:
        return self.get_one("events", identifier)

    def organisations(self, limit: int = 20, offset: int = 0) -> Page:
        return self.list("organisations", limit, offset)

    def organisation(self, identifier: int) -> dict:
        return self.get_one("organisations", identifier)

    def business_walls(self, limit: int = 20, offset: int = 0) -> Page:
        return self.list("business-walls", limit, offset)

    def business_wall(self, identifier: str) -> dict:
        return self.get_one("business-walls", identifier)

    def members(self, limit: int = 20, offset: int = 0) -> Page:
        return self.list("members", limit, offset)

    def member(self, identifier: int) -> dict:
        return self.get_one("members", identifier)

    # --- owner-scoped self & writes --------------------------------------
    # The `/me` reads need `read:self`; create/update/publish/delete need
    # `write:content`. `collection` is a path segment such as
    # "me/press-releases", "me/articles" or "me/events".

    def me(self) -> dict:
        """Fetch the authenticated user's own profile (``GET /me``)."""
        return self._request(f"{API_PREFIX}/me")

    def create(self, collection: str, data: dict[str, Any]) -> dict:
        """Create a resource (``POST /{collection}``)."""
        return self._request(collection, method="POST", json_body=data)

    def update(self, collection: str, identifier: Any, data: dict[str, Any]) -> dict:
        """Partially update a resource (``PATCH /{collection}/{id}``)."""
        return self._request(
            f"{collection}/{identifier}", method="PATCH", json_body=data
        )

    def delete(self, collection: str, identifier: Any) -> None:
        """Delete a resource (``DELETE /{collection}/{id}``)."""
        self._request(f"{collection}/{identifier}", method="DELETE")

    def publish(self, collection: str, identifier: Any) -> dict:
        """Publish a resource (``POST /{collection}/{id}/publish``)."""
        return self._request(f"{collection}/{identifier}/publish", method="POST")

    def unpublish(self, collection: str, identifier: Any) -> dict:
        """Unpublish a resource (``POST /{collection}/{id}/unpublish``)."""
        return self._request(f"{collection}/{identifier}/unpublish", method="POST")
