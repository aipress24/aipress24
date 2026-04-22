# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for the content-addressed /media endpoint.

These tests substitute the session-wide "s3" backend with a local-
filesystem backend pointing at a per-test tempdir, so they run without
MinIO.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING

import fsspec
import pytest
from advanced_alchemy.types.file_object import storages
from advanced_alchemy.types.file_object.backends.fsspec import FSSpecBackend
from flask import session
from flask_security import login_user

from app.models.auth import User

if TYPE_CHECKING:
    from collections.abc import Iterator

    from flask import Flask
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


# 1x1 PNG
TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
    b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.fixture
def anon_client(app: Flask) -> FlaskClient:
    return app.test_client()


@pytest.fixture
def client(app: Flask, db_session: Session) -> FlaskClient:
    user = User(email="media-test@example.com", active=True)
    user.photo = b""
    db_session.add(user)
    db_session.flush()

    c = app.test_client()
    with app.test_request_context():
        login_user(user)
        with c.session_transaction() as sess:
            for key, value in session.items():
                sess[key] = value
    return c


@pytest.fixture
def local_media_backend(tmp_path: Path) -> Iterator[Path]:
    """Swap the "s3" backend for a local-fs one rooted at tmp_path.

    Restores the original backend on teardown. Files dropped into
    tmp_path are then fetchable via backend.get_content(<filename>).
    """
    original = storages.get_backend("s3")
    local_fs = fsspec.filesystem("file")
    storages.register_backend(
        FSSpecBackend(fs=local_fs, key="s3", prefix=str(tmp_path))
    )
    yield tmp_path
    storages.register_backend(original)


def _put(storage_dir: Path, content: bytes, ext: str = "png") -> str:
    """Write content under its sha256-based name; return the storage name."""
    storage_name = f"{hashlib.sha256(content).hexdigest()}.{ext}"
    (storage_dir / storage_name).write_bytes(content)
    return storage_name


class TestServe:
    def test_serves_existing_file(self, client: FlaskClient, local_media_backend: Path):
        storage_name = _put(local_media_backend, TINY_PNG)
        response = client.get(f"/media/{storage_name}")
        assert response.status_code == 200
        assert response.data == TINY_PNG
        assert response.mimetype == "image/png"

    def test_guesses_mime_from_extension(
        self, client: FlaskClient, local_media_backend: Path
    ):
        storage_name = _put(local_media_backend, b"hello", ext="txt")
        response = client.get(f"/media/{storage_name}")
        assert response.status_code == 200
        assert response.mimetype == "text/plain"

    def test_unknown_hash_returns_404(
        self, client: FlaskClient, local_media_backend: Path
    ):
        missing = "0" * 64 + ".png"
        response = client.get(f"/media/{missing}")
        assert response.status_code == 404

    def test_anonymous_access_is_denied(
        self, anon_client: FlaskClient, local_media_backend: Path
    ):
        # Nothing on this backend is truly public — KYC docs and
        # justificatifs share it. The hash is not a substitute for auth.
        storage_name = _put(local_media_backend, TINY_PNG)
        response = anon_client.get(f"/media/{storage_name}")
        assert response.status_code == 401


class TestValidation:
    @pytest.mark.parametrize(
        "bad_name",
        [
            "too-short.png",
            "../etc/passwd",
            "not_a_hex_" + "z" * 54 + ".png",
            "x" * 64,  # hex but wrong length (counts but not 64 real hex)
        ],
    )
    def test_rejects_malformed_storage_name(
        self, client: FlaskClient, local_media_backend: Path, bad_name: str
    ):
        response = client.get(f"/media/{bad_name}")
        assert response.status_code == 404


class TestCaching:
    def test_emits_immutable_cache_control(
        self, client: FlaskClient, local_media_backend: Path
    ):
        storage_name = _put(local_media_backend, TINY_PNG)
        response = client.get(f"/media/{storage_name}")
        cache_control = response.headers["Cache-Control"]
        assert "private" in cache_control
        assert "immutable" in cache_control
        assert "max-age=31536000" in cache_control
        # Flask-Security's default appends `no-store` to every authed
        # response, which defeats caching on immutable assets; we drop
        # it via SECURITY_CACHE_CONTROL config.
        assert "no-store" not in cache_control
        # Flask-Security's upstream add_cache_control writes directives
        # via dict-style access, producing malformed `private=True`; our
        # patched hook uses attribute setters so the standalone directive
        # serialises as a bare token. This asserts the patch is active.
        assert "private=True" not in cache_control

    def test_emits_etag_from_sha256(
        self, client: FlaskClient, local_media_backend: Path
    ):
        storage_name = _put(local_media_backend, TINY_PNG)
        sha256 = storage_name.split(".", 1)[0]
        response = client.get(f"/media/{storage_name}")
        assert sha256 in response.headers["ETag"]

    def test_conditional_get_returns_304(
        self, client: FlaskClient, local_media_backend: Path
    ):
        storage_name = _put(local_media_backend, TINY_PNG)
        first = client.get(f"/media/{storage_name}")
        etag = first.headers["ETag"]
        second = client.get(f"/media/{storage_name}", headers={"If-None-Match": etag})
        assert second.status_code == 304
        assert second.data == b""
