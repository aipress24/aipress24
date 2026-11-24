# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: Apache-2.0
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
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Iterator, Sequence
from typing import Any, Generic, TypeVar, cast

# COLLECTIONS and the per-resource TypedDict models are generated from the
# OpenAPI spec (see ../generate.py); a unit test keeps them in sync.
from ._generated import (
    COLLECTIONS,
    Article,
    BusinessWall,
    Event,
    Member,
    Organisation,
    PressRelease,
    PressReleaseImage,
    PressReleaseVocabularies,
    SelfProfile,
)

__all__ = [
    "COLLECTIONS",
    "ApiError",
    "Article",
    "BusinessWall",
    "Client",
    "Event",
    "Member",
    "Organisation",
    "Page",
    "PressRelease",
    "PressReleaseImage",
    "PressReleaseVocabularies",
    "SelfProfile",
]

__version__ = "0.1.0"

DEFAULT_BASE_URL = "https://aipress24.com"
API_PREFIX = "/api/v1"

_ABSOLUTE_URL = re.compile(r"[a-z][a-z0-9+.-]*://", re.IGNORECASE)

Item = TypeVar("Item")


class ApiError(Exception):
    """Raised for any non-2xx API response."""

    def __init__(self, status: int, payload: dict[str, Any] | None) -> None:
        self.status = status
        self.payload = payload or {}
        message = self.payload.get("message") or self.payload.get("status") or "error"
        super().__init__(f"HTTP {status}: {message}")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Report a redirect instead of sending the token wherever it points."""

    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


_opener = urllib.request.build_opener(_NoRedirect)


class Page(Generic[Item]):
    """One page of a collection, with helpers to walk to the next page."""

    def __init__(self, client: Client, body: dict[str, Any]) -> None:
        self._client = client
        self.items: list[Item] = body.get("items", [])
        self.total: int = body.get("total", len(self.items))
        self.limit: int = body.get("limit", len(self.items))
        self.offset: int = body.get("offset", 0)
        self.links: dict[str, dict[str, str]] = body.get("_links", {})

    @property
    def has_next(self) -> bool:
        return "next" in self.links

    def next_page(self) -> Page[Item] | None:
        href = self.links.get("next", {}).get("href")
        if not href:
            return None
        return Page(self._client, self._client._request(href))

    def __iter__(self) -> Iterator[Item]:
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
        if not base_url.startswith(("https://", "http://")):
            msg = f"base_url must be an http(s) URL: {base_url!r}"
            raise ValueError(msg)
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
        request = urllib.request.Request(url, headers=headers, method=method, data=data)
        try:
            with _opener.open(request, timeout=self.timeout) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.read()

    def _url(self, path: str, params: dict[str, Any] | None = None) -> str:
        if _ABSOLUTE_URL.match(path):
            if not path.startswith(f"{self.base_url}/"):
                msg = f"Refusing to send the token to another origin: {path}"
                raise ValueError(msg)
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
        multipart: tuple[str, bytes] | None = None,
    ) -> dict[str, Any]:
        url = self._url(path, params)
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }
        data: bytes | None = None
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif multipart is not None:
            headers["Content-Type"], data = multipart
        status, raw = self._open(url, headers, method=method, data=data)
        try:
            body = json.loads(raw) if raw else {}
        except ValueError:
            body = {}
        if not 200 <= status < 300:
            raise ApiError(status, body)
        return body

    # --- generic resource access -----------------------------------------

    def root(self) -> dict[str, Any]:
        """Fetch the API discovery document (link relations, docs URLs)."""
        return self._request(f"{API_PREFIX}/")

    def list(
        self, collection: str, limit: int = 20, offset: int = 0
    ) -> Page[dict[str, Any]]:
        """Fetch one page of a collection."""
        return Page(self, self._request(collection, {"limit": limit, "offset": offset}))

    def get_one(self, collection: str, identifier: Any) -> dict[str, Any]:
        """Fetch a single resource by id."""
        return self._request(f"{collection}/{identifier}")

    def iter(self, collection: str, limit: int = 50) -> Iterator[dict[str, Any]]:
        """Iterate over every item in a collection, following ``next`` links."""
        page: Page[dict[str, Any]] | None = self.list(collection, limit=limit, offset=0)
        while page is not None:
            yield from page.items
            page = page.next_page()

    # --- named convenience methods ---------------------------------------

    def articles(self, limit: int = 20, offset: int = 0) -> Page[Article]:
        return cast("Page[Article]", self.list("articles", limit, offset))

    def article(self, identifier: int) -> Article:
        return cast("Article", self.get_one("articles", identifier))

    def press_releases(self, limit: int = 20, offset: int = 0) -> Page[PressRelease]:
        return cast("Page[PressRelease]", self.list("press-releases", limit, offset))

    def press_release(self, identifier: int) -> PressRelease:
        return cast("PressRelease", self.get_one("press-releases", identifier))

    def events(self, limit: int = 20, offset: int = 0) -> Page[Event]:
        return cast("Page[Event]", self.list("events", limit, offset))

    def event(self, identifier: int) -> Event:
        return cast("Event", self.get_one("events", identifier))

    def organisations(self, limit: int = 20, offset: int = 0) -> Page[Organisation]:
        return cast("Page[Organisation]", self.list("organisations", limit, offset))

    def organisation(self, identifier: int) -> Organisation:
        return cast("Organisation", self.get_one("organisations", identifier))

    def business_walls(self, limit: int = 20, offset: int = 0) -> Page[BusinessWall]:
        return cast("Page[BusinessWall]", self.list("business-walls", limit, offset))

    def business_wall(self, identifier: str) -> BusinessWall:
        return cast("BusinessWall", self.get_one("business-walls", identifier))

    def members(self, limit: int = 20, offset: int = 0) -> Page[Member]:
        return cast("Page[Member]", self.list("members", limit, offset))

    def member(self, identifier: int) -> Member:
        return cast("Member", self.get_one("members", identifier))

    # --- owner-scoped self & writes --------------------------------------
    # The `/me` reads need `read:self`; create/update/publish/delete need
    # `write:content`. `collection` is a path segment such as
    # "me/press-releases", "me/articles" or "me/events".

    def me(self) -> SelfProfile:
        """Fetch the authenticated user's own profile (``GET /me``)."""
        return cast("SelfProfile", self._request(f"{API_PREFIX}/me"))

    def create(self, collection: str, data: dict[str, Any]) -> dict[str, Any]:
        """Create a resource (``POST /{collection}``)."""
        return self._request(collection, method="POST", json_body=data)

    def update(
        self, collection: str, identifier: Any, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Partially update a resource (``PATCH /{collection}/{id}``)."""
        return self._request(
            f"{collection}/{identifier}", method="PATCH", json_body=data
        )

    def delete(self, collection: str, identifier: Any) -> None:
        """Delete a resource (``DELETE /{collection}/{id}``)."""
        self._request(f"{collection}/{identifier}", method="DELETE")

    def publish(self, collection: str, identifier: Any) -> dict[str, Any]:
        """Publish a resource (``POST /{collection}/{id}/publish``)."""
        return self._request(f"{collection}/{identifier}/publish", method="POST")

    def unpublish(self, collection: str, identifier: Any) -> dict[str, Any]:
        """Unpublish a resource (``POST /{collection}/{id}/unpublish``)."""
        return self._request(f"{collection}/{identifier}/unpublish", method="POST")

    # --- press-release helpers -------------------------------------------

    def press_release_vocabularies(self) -> PressReleaseVocabularies:
        """Fetch the values accepted to classify a press release."""
        return cast(
            "PressReleaseVocabularies", self._request("vocabularies/press-releases")
        )

    def press_release_images(self, identifier: int) -> Sequence[PressReleaseImage]:
        """List the carousel of one of your press releases, cover first."""
        return self._request(_images_path(identifier))["items"]

    def add_press_release_image(
        self,
        identifier: int,
        content: bytes,
        filename: str,
        caption: str = "",
        copyright: str = "",
    ) -> PressReleaseImage:
        """Append an image to the carousel of one of your press releases."""
        body = self._request(
            _images_path(identifier),
            method="POST",
            multipart=_encode_multipart(
                {"caption": caption, "copyright": copyright}, filename, content
            ),
        )
        return cast("PressReleaseImage", body)

    def delete_press_release_image(self, identifier: int, image_id: int) -> None:
        """Remove an image from the carousel of one of your press releases."""
        self._request(f"{_images_path(identifier)}/{image_id}", method="DELETE")


def _images_path(identifier: int) -> str:
    return f"me/press-releases/{identifier}/images"


def _encode_multipart(
    fields: dict[str, str], filename: str, content: bytes
) -> tuple[str, bytes]:
    """Encode a form with one ``image`` file, as ``(content type, body)``."""
    boundary = uuid.uuid4().hex
    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'
        f"{value}\r\n"
        for name, value in fields.items()
    ]
    # Escaped as browsers do, so that a filename cannot add headers.
    safe = filename.replace('"', "%22").replace("\r", "%0D").replace("\n", "%0A")
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="image"; '
        f'filename="{safe}"\r\nContent-Type: application/octet-stream\r\n\r\n'
    )
    head = "".join(parts).encode()
    return (
        f"multipart/form-data; boundary={boundary}",
        head + content + f"\r\n--{boundary}--\r\n".encode(),
    )
