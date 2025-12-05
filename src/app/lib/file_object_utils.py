# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-onlyfrom __future__ import annotations

from __future__ import annotations

from typing import Any

from advanced_alchemy.types import FileObject


def _deserialize_file_object(file_data: dict[str, Any] | None) -> FileObject | None:
    if (
        isinstance(file_data, dict)
        and file_data.get("backend")
        and file_data.get("filename")
    ):
        try:
            return FileObject(
                backend=file_data["backend"],
                filename=file_data["filename"],
                to_filename=file_data.get("to_filename"),
                content_type=file_data.get("content_type"),
                size=file_data.get("size"),
                last_modified=file_data.get("last_modified"),
                checksum=file_data.get("checksum"),
                etag=file_data.get("etag"),
                version_id=file_data.get("version_id"),
                metadata=file_data.get("metadata"),
            )
        except (KeyError, ValueError, TypeError):
            return None
    return None
