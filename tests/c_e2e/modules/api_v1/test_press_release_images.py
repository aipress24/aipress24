# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""The press-release carousel, through ``/me/press-releases/{id}/images``."""

from __future__ import annotations

import hashlib
from io import BytesIO
from typing import TYPE_CHECKING

import pytest
import sqlalchemy as sa
from PIL import Image

from app.modules.wip.models import ComImage
from app.modules.wire.models import PressReleasePost
from app.settings.constants import MAX_IMAGE_SIZE

from .test_write import _auth, _create

if TYPE_CHECKING:
    from pathlib import Path
    from types import SimpleNamespace

    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session
    from werkzeug.test import TestResponse


def _image(fmt: str = "PNG", color: str = "red") -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (4, 4), color).save(buffer, fmt)
    return buffer.getvalue()


def _digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


pytestmark = pytest.mark.usefixtures("media_dir")


def _upload(
    client: FlaskClient,
    token: str,
    pr_id: int,
    content: bytes,
    filename: str = "photo.png",
    **form: str,
) -> TestResponse:
    return client.post(
        f"/api/v1/me/press-releases/{pr_id}/images",
        data={"image": (BytesIO(content), filename), **form},
        headers=_auth(token),
    )


def _list(client: FlaskClient, token: str, pr_id: int) -> list[dict]:
    resp = client.get(f"/api/v1/me/press-releases/{pr_id}/images", headers=_auth(token))
    assert resp.status_code == 200
    return resp.get_json()["items"]


def test_upload_then_list_in_carousel_order(
    client: FlaskClient, wseed: SimpleNamespace, media_dir: Path
) -> None:
    token = wseed.author_token
    pr_id = _create(client, token)["id"]
    first = _image(color="red")

    resp = _upload(
        client, token, pr_id, first, "a.png", caption="Légende", copyright="© Acme"
    )
    assert resp.status_code == 201, resp.get_json()
    second = _image(color="blue")
    _upload(client, token, pr_id, second, "b.png")

    items = _list(client, token, pr_id)
    assert [(i["sha256"], i["position"]) for i in items] == [
        (_digest(first), 0),
        (_digest(second), 1),
    ]
    assert items[0]["caption"] == "Légende"
    assert items[0]["copyright"] == "© Acme"
    assert (media_dir / f"{_digest(first)}.png").read_bytes() == first


@pytest.mark.parametrize(
    ("fmt", "suffix"),
    [
        ("PNG", ".png"),
        ("JPEG", ".jpg"),
        ("GIF", ".gif"),
        ("WEBP", ".webp"),
        ("AVIF", ".avif"),
    ],
)
def test_stored_type_follows_the_bytes_not_the_filename(
    client: FlaskClient, wseed: SimpleNamespace, media_dir: Path, fmt: str, suffix: str
) -> None:
    token = wseed.author_token
    pr_id = _create(client, token)["id"]
    content = _image(fmt)

    assert _upload(client, token, pr_id, content, "x.pdf").status_code == 201

    assert (media_dir / f"{_digest(content)}{suffix}").exists()


@pytest.mark.parametrize(
    ("content", "status"),
    [
        (b"", 422),
        (b"not an image", 422),
        (b'<svg xmlns="http://www.w3.org/2000/svg"/>', 422),
        (_image("BMP"), 422),
        (b"\x89PNG" + b"0" * MAX_IMAGE_SIZE, 413),
    ],
    ids=["empty", "text", "svg", "bmp", "too-large"],
)
def test_refuses_what_is_not_a_supported_image(
    client: FlaskClient, wseed: SimpleNamespace, content: bytes, status: int
) -> None:
    token = wseed.author_token
    pr_id = _create(client, token)["id"]

    assert _upload(client, token, pr_id, content).status_code == status
    assert _list(client, token, pr_id) == []


def test_upload_requires_a_file(client: FlaskClient, wseed: SimpleNamespace) -> None:
    pr_id = _create(client, wseed.author_token)["id"]
    resp = client.post(
        f"/api/v1/me/press-releases/{pr_id}/images",
        data={"caption": "x"},
        content_type="multipart/form-data",
        headers=_auth(wseed.author_token),
    )
    assert resp.status_code == 422


def test_delete_closes_the_gap_and_keeps_the_shared_file(
    client: FlaskClient, wseed: SimpleNamespace, db_session: Session, media_dir: Path
) -> None:
    token = wseed.author_token
    pr_id = _create(client, token)["id"]
    content = _image()
    first = _upload(client, token, pr_id, content, "a.png").get_json()["id"]
    second = _image(color="blue")
    _upload(client, token, pr_id, second, "b.png")

    resp = client.delete(
        f"/api/v1/me/press-releases/{pr_id}/images/{first}", headers=_auth(token)
    )

    assert resp.status_code == 204
    assert [(i["sha256"], i["position"]) for i in _list(client, token, pr_id)] == [
        (_digest(second), 0)
    ]
    assert db_session.get(ComImage, first) is None
    # Storage is content-addressed: another row may point at the same bytes.
    assert (media_dir / f"{_digest(content)}.png").exists()


def test_the_public_cover_follows_the_carousel(
    client: FlaskClient, wseed: SimpleNamespace, db_session: Session
) -> None:
    token = wseed.author_token
    pr_id = _create(client, token, contenu="<p>Body</p>")["id"]
    client.post(f"/api/v1/me/press-releases/{pr_id}/publish", headers=_auth(token))

    def cover() -> int | None:
        db_session.expire_all()
        return db_session.scalar(
            sa.select(PressReleasePost.image_id).where(
                PressReleasePost.newsroom_id == pr_id
            )
        )

    assert cover() is None
    image_id = _upload(client, token, pr_id, _image()).get_json()["id"]
    assert cover() == image_id
    client.delete(
        f"/api/v1/me/press-releases/{pr_id}/images/{image_id}", headers=_auth(token)
    )
    assert cover() is None


def test_another_users_images_are_out_of_reach(
    client: FlaskClient, wseed: SimpleNamespace
) -> None:
    pr_id = _create(client, wseed.author_token)["id"]
    image_id = _upload(client, wseed.author_token, pr_id, _image()).get_json()["id"]
    base = f"/api/v1/me/press-releases/{pr_id}/images"
    other = _auth(wseed.other_token)

    assert client.get(base, headers=other).status_code == 404
    assert _upload(client, wseed.other_token, pr_id, _image()).status_code == 404
    assert client.delete(f"{base}/{image_id}", headers=other).status_code == 404
    assert len(_list(client, wseed.author_token, pr_id)) == 1


def test_an_image_is_only_reachable_through_its_own_release(
    client: FlaskClient, wseed: SimpleNamespace
) -> None:
    token = wseed.author_token
    pr_id = _create(client, token)["id"]
    other_pr = _create(client, token)["id"]
    image_id = _upload(client, token, pr_id, _image()).get_json()["id"]

    resp = client.delete(
        f"/api/v1/me/press-releases/{other_pr}/images/{image_id}", headers=_auth(token)
    )
    assert resp.status_code == 404


def test_writes_need_the_write_scope(
    client: FlaskClient, wseed: SimpleNamespace
) -> None:
    pr_id = _create(client, wseed.author_token)["id"]
    image_id = _upload(client, wseed.author_token, pr_id, _image()).get_json()["id"]
    read_only = wseed.author_read_only

    assert _list(client, read_only, pr_id)
    assert _upload(client, read_only, pr_id, _image()).status_code == 403
    resp = client.delete(
        f"/api/v1/me/press-releases/{pr_id}/images/{image_id}", headers=_auth(read_only)
    )
    assert resp.status_code == 403
