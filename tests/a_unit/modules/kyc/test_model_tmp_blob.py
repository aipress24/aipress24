# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.modules.kyc.temporary_blob import delete_tmp_blob, pop_tmp_blob, store_tmp_blob


def test_store(app, db) -> None:
    with app.app_context():
        blob_id = store_tmp_blob("test.jpg", b"aaaa")
        assert isinstance(blob_id, int)


def test_store_pop(app, db) -> None:
    with app.app_context():
        blob_id = store_tmp_blob("test.jpg", b"aaaa")
        assert isinstance(blob_id, int)
        name, _uuid, content = pop_tmp_blob(blob_id)
        assert name == "test.jpg"
        assert content == b"aaaa"
        name, _uuid, content = pop_tmp_blob(blob_id)
        assert name == ""  # PLC1901
        assert content == b""


def test_pop_none(app, db) -> None:
    with app.app_context():
        name, _uuid, content = pop_tmp_blob(123456)
        assert name == ""
        assert content == b""


def test_delete(app, db) -> None:
    with app.app_context():
        blob_id = store_tmp_blob("test.jpg", b"aaaa")
        assert isinstance(blob_id, int)
        delete_tmp_blob(blob_id)
        name, _uuid, content = pop_tmp_blob(blob_id)
        assert name == ""
        assert content == b""


def test_delete_non_exist(app, db) -> None:
    with app.app_context():
        delete_tmp_blob(123456)
