# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""Wall posts through the API."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import arrow
import pytest
import sqlalchemy as sa
from flask.testing import FlaskClient
from PIL import Image
from sqlalchemy.orm import Session
from werkzeug.test import TestResponse

from app.models.short_post import ShortPost, ShortPostImage
from app.modules.api_v1 import writes

from .conftest import _mint_token

URL = "/api/v1/me/posts"
OLD = "2012-05-01T10:00:00+00:00"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _post(client: FlaskClient, token: str, **data) -> TestResponse:
    return client.post(
        URL, data=data, headers=_auth(token), content_type="multipart/form-data"
    )


def _png(color: str = "red") -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (2, 2), color).save(buffer, "PNG")
    return buffer.getvalue()


@pytest.fixture
def token(wseed: SimpleNamespace) -> str:
    return wseed.author_token


def test_a_post_round_trips(client: FlaskClient, token: str) -> None:
    text = "R&D <b>\n\nhttps://x.test/?a=1&b=2"
    response = _post(client, token, text=f" {text} ")
    assert response.status_code == 201
    created = response.get_json()
    assert created["text"] == text
    assert created["external_ref"] is None
    assert arrow.get(created["published_at"]) > arrow.utcnow().shift(minutes=-1)
    page = created["_links"]["page"]["href"]
    assert page.startswith("/swork/posts/x")

    url = created["_links"]["self"]["href"]
    assert client.get(url, headers=_auth(token)).get_json() == created
    listed = client.get(URL, headers=_auth(token)).get_json()
    assert listed["items"] == [created]


def test_an_old_post_is_imported(client: FlaskClient, token: str) -> None:
    reference = "https://social.test/@me/1"
    _post(client, token, text="autre")
    created = _post(
        client, token, text="Ancien", published_at=OLD, external_ref=reference
    ).get_json()
    assert arrow.get(created["published_at"]) == arrow.get(OLD)
    found = client.get(
        URL, query_string={"external_ref": reference}, headers=_auth(token)
    ).get_json()
    assert [item["id"] for item in found["items"]] == [created["id"]]


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"text": "  "},
        {"text": "x", "published_at": OLD},
        {"text": "x", "published_at": "1999-01-01T00:00:00Z", "external_ref": "r"},
        {"text": "x", "published_at": "2999-01-01T00:00:00Z", "external_ref": "r"},
        {"text": "x", "published_at": "2012-05-01", "external_ref": "r"},
        {"text": "x", "external_ref": ""},
        {"text": "x", "external_ref": "r" * 501},
        {"text": "x" * 10_001},
        {"text": "x", "owner_id": "1"},
    ],
)
def test_invalid_posts(
    client: FlaskClient, token: str, db_session: Session, data: dict
) -> None:
    assert _post(client, token, **data).status_code == 422
    assert db_session.scalars(sa.select(ShortPost)).all() == []


def test_a_reference_is_used_once(
    client: FlaskClient, wseed: SimpleNamespace, token: str
) -> None:
    created = _post(client, token, text="a", external_ref="r").get_json()
    assert _post(client, token, text="b", external_ref="r").status_code == 409
    other = _post(client, wseed.other_token, text="c", external_ref="r")
    assert other.status_code == 201
    url = f"{URL}/{created['id']}"
    assert client.delete(url, headers=_auth(token)).status_code == 204
    assert client.get(url, headers=_auth(token)).status_code == 404
    assert _post(client, token, text="b", external_ref="r").status_code == 201


def test_images_come_with_the_post(
    client: FlaskClient, token: str, db_session: Session, media_dir: Path
) -> None:
    files = [(BytesIO(_png("red")), "a.svg"), (BytesIO(_png("blue")), "b.png")]
    response = _post(client, token, images=files, captions=["Rouge", "Bleu"])
    assert response.status_code == 201
    images = response.get_json()["images"]
    assert [image["caption"] for image in images] == ["Rouge", "Bleu"]
    assert [image["position"] for image in images] == [0, 1]
    assert all(len(image["sha256"]) == 64 for image in images)
    post = db_session.scalars(sa.select(ShortPost)).one()
    assert all(image.url.endswith(".png") for image in post.images)


@pytest.mark.parametrize(
    ("contents", "status"),
    [
        ([b"<svg></svg>"], 422),
        ([b"x" * 4 * 1024 * 1024], 413),
        ([_png()] * 13, 422),
        ([_png(), b"text"], 422),
    ],
    ids=["svg", "large", "many", "second"],
)
def test_refused_images_create_nothing(
    client: FlaskClient,
    token: str,
    db_session: Session,
    media_dir: Path,
    contents: list[bytes],
    status: int,
) -> None:
    files = [(BytesIO(content), "a.png") for content in contents]
    assert _post(client, token, text="x", images=files).status_code == status
    assert db_session.scalars(sa.select(ShortPost)).all() == []
    assert db_session.scalars(sa.select(ShortPostImage)).all() == []


def test_scopes(
    client: FlaskClient, wseed: SimpleNamespace, db_session: Session
) -> None:
    def status(*scopes: str) -> tuple[int, int, int]:
        token = _mint_token(db_session, wseed.author, list(scopes))
        created = _post(client, token, text="x")
        reading = client.get(URL, headers=_auth(token))
        deleting = client.delete(f"{URL}/{target}", headers=_auth(token))
        return created.status_code, reading.status_code, deleting.status_code

    target = _post(client, wseed.author_token, text="x").get_json()["id"]
    assert status("write:content", "read:self") == (403, 200, 403)
    assert status("write:social") == (201, 403, 204)


def test_another_members_post_is_out_of_reach(
    client: FlaskClient, wseed: SimpleNamespace, token: str, db_session: Session
) -> None:
    created = _post(client, token, text="x").get_json()
    url = f"{URL}/{created['id']}"
    other = _auth(wseed.other_token)
    assert client.get(url, headers=other).status_code == 404
    assert client.delete(url, headers=other).status_code == 404
    assert client.get(URL, headers=other).get_json()["items"] == []


def test_any_member_may_post(client: FlaskClient, wseed: SimpleNamespace) -> None:
    assert _post(client, wseed.journalist_token, text="x").status_code == 201


def test_there_is_a_limit_for_new_posts_and_one_for_imports(
    client: FlaskClient,
    wseed: SimpleNamespace,
    token: str,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(writes, "MAX_NEW_POSTS", 1)
    monkeypatch.setattr(writes, "MAX_IMPORTED_POSTS", 2)

    def new() -> int:
        return _post(client, token, text="x").status_code

    def imported(reference: str) -> int:
        return _post(
            client, token, text="x", published_at=OLD, external_ref=reference
        ).status_code

    assert [new(), new()] == [201, 429]
    assert [imported("a"), imported("b"), imported("c")] == [201, 201, 429]
    # Deleting does not give room, another account has its own, and time passes.
    for post in db_session.scalars(sa.select(ShortPost)):
        client.delete(f"{URL}/{post.id}", headers=_auth(token))
    assert (new(), imported("d")) == (429, 429)
    assert _post(client, wseed.other_token, text="x").status_code == 201
    for post in db_session.scalars(sa.select(ShortPost)):
        post.created_at = arrow.utcnow().shift(hours=-25)
    db_session.commit()
    assert (new(), imported("d")) == (201, 201)
