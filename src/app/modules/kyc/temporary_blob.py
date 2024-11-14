# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-onlyfrom __future__ import annotations

from __future__ import annotations

from uuid import uuid4

from app.flask.extensions import db
from app.models.kyc_tmp_blob import KYCTmpBlob


def store_tmp_blob(filename: str, content: bytes) -> int:
    if not content or not filename:
        return 0
    blob = KYCTmpBlob(
        name=filename,
        uuid=uuid4().hex,
        content=content,
    )
    db_session = db.session
    db_session.add(blob)
    db_session.commit()
    return blob.id


def pop_tmp_blob(blob_id: int | str | None) -> tuple[str, str, bytes]:
    content = b""
    name = ""
    uuid = ""
    if blob_id is None:
        return name, uuid, content
    db_session = db.session
    blob = db_session.get(KYCTmpBlob, blob_id)
    if blob:
        content = blob.content
        name = blob.name
        uuid = blob.uuid
        db_session.delete(blob)
        db_session.commit()
    return name, uuid, content


def read_tmp_blob(blob_id: int | str | None) -> tuple[str, str, bytes]:
    content = b""
    name = ""
    uuid = ""
    if blob_id is None:
        return name, content
    db_session = db.session
    blob = db_session.get(KYCTmpBlob, blob_id)
    if blob:
        content = blob.content
        name = blob.name
        uuid = blob.uuid
    return name, uuid, content


def delete_tmp_blob(blob_id: int | str | None) -> str:
    uuid = ""
    if blob_id is None:
        return uuid
    db_session = db.session
    blob = db_session.get(KYCTmpBlob, blob_id)
    if blob:
        uuid = blob.uuid
        db_session.delete(blob)
        db_session.commit()
    return uuid
