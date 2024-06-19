# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import jsonify, request, send_file, url_for
from svcs.flask import container
from werkzeug import Response

from app.services.blobs import BlobService

from . import blueprint


@blueprint.get("/blobs/<id>")
def get_blob(id: str) -> Response:
    assert "/" not in id

    blob_service = container.get(BlobService)
    blob_path = blob_service.get_path(id)
    return send_file(blob_path)


@blueprint.post("/blobs/")
def post_blob() -> Response:
    blob_service = container.get(BlobService)
    blob = blob_service.save(request.files["file"])
    url = url_for(".get_blob", id=blob.id)
    href = url_for(".get_blob", id=blob.id)
    return jsonify({"url": url, "href": href})
