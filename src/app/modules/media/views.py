# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import mimetypes
import re
from io import BytesIO

from advanced_alchemy.types.file_object import storages
from flask import abort, send_file
from werkzeug.wrappers import Response

from . import blueprint

# Storage names produced by create_file_object() — 64 hex chars (sha256)
# plus optional extension. Validated here to keep the endpoint from ever
# forwarding arbitrary paths to the storage backend.
_STORAGE_NAME_RE = re.compile(r"^[0-9a-f]{64}(?:\.[A-Za-z0-9]{1,10})?$")

# One year; the content at a given hash is immutable by construction.
_MAX_AGE = 31_536_000


@blueprint.route("/<string:storage_name>")
def serve(storage_name: str) -> Response:
    if not _STORAGE_NAME_RE.match(storage_name):
        abort(404)

    backend = storages.get_backend("s3")
    try:
        content = backend.get_content(storage_name)
    except (FileNotFoundError, OSError):
        abort(404)

    mimetype, _ = mimetypes.guess_type(storage_name)
    sha256 = storage_name.split(".", 1)[0]
    # Cache-Control is set centrally by the blueprint's after_request hook
    # so it survives Flask-Security's global no-store mutation.
    return send_file(
        BytesIO(content),
        mimetype=mimetype or "application/octet-stream",
        download_name=storage_name,
        etag=sha256,
        max_age=_MAX_AGE,
        conditional=True,
    )
