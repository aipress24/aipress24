"""API endpoints for file uploads (blobs)."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import request

from app.lib.file_object_utils import create_file_object

from . import blueprint


@blueprint.post("/trix_blobs/")
def upload_blob() -> tuple[dict, int]:
    """Upload a file and return its URL, for Trix editor."""
    if "file" not in request.files:
        return {"error": "No file provided"}, 400

    file = request.files["file"]
    if not file.filename:
        return {"error": "Empty filename"}, 400
    filename = file.filename

    file_obj = create_file_object(
        content=file.read(),
        original_filename=filename,
        content_type=file.content_type or "application/octet-stream",
    )
    saved_file_obj = file_obj.save()

    expires_in = 300000000  # ~10years
    url = saved_file_obj.sign(expires_in=expires_in, for_upload=False)

    return {
        "url": url,
        "href": url,
        "filename": file.filename,
    }, 200
