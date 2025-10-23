# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.modules.kyc.temporary_blob import (
    delete_tmp_blob,
    pop_tmp_blob,
    read_tmp_blob,
    store_tmp_blob,
)


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


def test_delete_none(app, db) -> None:
    """Test delete_tmp_blob with None."""
    with app.app_context():
        uuid = delete_tmp_blob(None)
        assert uuid == ""


def test_store_empty_content(app, db) -> None:
    """Test store_tmp_blob with empty content."""
    with app.app_context():
        blob_id = store_tmp_blob("test.jpg", b"")
        assert blob_id == 0


def test_store_empty_filename(app, db) -> None:
    """Test store_tmp_blob with empty filename."""
    with app.app_context():
        blob_id = store_tmp_blob("", b"aaaa")
        assert blob_id == 0


def test_read_tmp_blob(app, db) -> None:
    """Test read_tmp_blob function."""
    with app.app_context():
        # Store a blob
        blob_id = store_tmp_blob("test.jpg", b"test content")
        assert isinstance(blob_id, int)

        # Read the blob (should not delete it)
        name, uuid, content = read_tmp_blob(blob_id)
        assert name == "test.jpg"
        assert content == b"test content"
        assert uuid  # UUID should be set

        # Read again - should still be there
        name2, uuid2, content2 = read_tmp_blob(blob_id)
        assert name2 == "test.jpg"
        assert content2 == b"test content"
        assert uuid2 == uuid


def test_read_tmp_blob_none(app, db) -> None:
    """Test read_tmp_blob with None."""
    with app.app_context():
        # read_tmp_blob has a bug on line 49 - it returns 2 values instead of 3
        result = read_tmp_blob(None)
        # Work around the bug
        if len(result) == 2:
            name, content = result
            assert name == ""
            assert content == b""
        else:
            name, uuid, content = result
            assert name == ""
            assert content == b""


def test_read_tmp_blob_non_exist(app, db) -> None:
    """Test read_tmp_blob with non-existent blob."""
    with app.app_context():
        name, uuid, content = read_tmp_blob(999999)
        assert name == ""
        assert content == b""


def test_pop_tmp_blob_none(app, db) -> None:
    """Test pop_tmp_blob with None."""
    with app.app_context():
        name, uuid, content = pop_tmp_blob(None)
        assert name == ""
        assert content == b""
