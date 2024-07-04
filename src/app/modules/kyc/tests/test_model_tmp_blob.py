# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

# ruff: noqa: PLC1901
from __future__ import annotations

from app.modules.kyc.temporary_blob import (
    delete_tmp_blob,
    pop_tmp_blob,
    store_tmp_blob,
)


def test_store(app) -> None:
    with app.app_context():
        blob_id = store_tmp_blob("test.jpg", b"aaaa")
        assert isinstance(blob_id, int)


def test_store_pop(app) -> None:
    with app.app_context():
        blob_id = store_tmp_blob("test.jpg", b"aaaa")
        assert isinstance(blob_id, int)
        name, content = pop_tmp_blob(blob_id)
        assert name == "test.jpg"
        assert content == b"aaaa"
        name, content = pop_tmp_blob(blob_id)
        assert name == ""  # PLC1901
        assert content == b""


def test_pop_none(app) -> None:
    with app.app_context():
        name, content = pop_tmp_blob(123456)
        assert name == ""
        assert content == b""


def test_delete(app) -> None:
    with app.app_context():
        blob_id = store_tmp_blob("test.jpg", b"aaaa")
        assert isinstance(blob_id, int)
        delete_tmp_blob(blob_id)
        name, content = pop_tmp_blob(blob_id)
        assert name == ""
        assert content == b""


def test_delete_non_exist(app) -> None:
    with app.app_context():
        delete_tmp_blob(123456)
