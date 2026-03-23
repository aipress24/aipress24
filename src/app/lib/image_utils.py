# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import base64
import binascii
import io
from typing import TYPE_CHECKING, NamedTuple

from PIL import Image, UnidentifiedImageError

if TYPE_CHECKING:
    from werkzeug.datastructures import FileStorage


class UploadedImageData(NamedTuple):
    """Extracted image data."""

    bytes: bytes
    filename: str
    content_type: str


def extract_image_from_request(
    file_storage: FileStorage | None = None,
    data_url: str | None = None,
    orig_filename: str | None = None,
) -> UploadedImageData | None:
    """Extract image bytes, filename and content type from request data.

    Handles both regular file uploads (FileStorage) and base64 data URLs
    from cropper.js widgets.

    Args:
        file_storage: FileStorage from request.files
        data_url: Base64 data URL from request.form
        orig_filename: Filename of orig image (for cropped images)

    Returns:
        UploadedImageData or None if no image found
    """
    # Regular file upload
    if file_storage is not None:
        image_bytes = file_storage.read()
        if image_bytes:
            return UploadedImageData(
                bytes=image_bytes,
                filename=file_storage.filename or "image.jpg",
                content_type=file_storage.content_type or "application/octet-stream",
            )
        return None

    # Handle base64 data URL from cropper
    if data_url and data_url.startswith("data:image/"):
        try:
            header, base64_data = data_url.split(",", 1)
            image_bytes = base64.b64decode(base64_data)
            content_type = header.split(";")[0].split(":")[1]
            suffix = content_type.split("/")[-1]

            if orig_filename:
                if f"image/{suffix}" in content_type and orig_filename.endswith(suffix):
                    filename = orig_filename
                else:
                    base_name = orig_filename.rsplit(".", 1)[0]
                    if suffix == "png":
                        filename = f"{base_name}.png"
                    else:
                        filename = f"{base_name}.jpg"
            else:
                filename = f"image.{suffix}"

            return UploadedImageData(
                bytes=image_bytes,
                filename=filename,
                content_type=content_type,
            )
        except (ValueError, binascii.Error):
            return None

    return None


def resized(src: bytes, max_size: int = 800) -> bytes:
    """Return a JPEG image content resized to larger side limit."""
    try:
        src_bytes = io.BytesIO(src)
        src_bytes.seek(0)
        img = Image.open(src_bytes)
        orig_size = img.size
        ratio = min(max_size / orig_size[0], max_size / orig_size[1])
        if ratio > 1.0:
            return src
        size = (round(orig_size[0] * ratio), round(orig_size[1] * ratio))
        img = img.resize(size)
        with io.BytesIO() as dest_bytes:
            img.save(dest_bytes, format="JPEG", quality=95)
            return dest_bytes.getvalue()
    except (UnidentifiedImageError, OSError):
        return src


def squared(src: bytes) -> bytes:
    """Return a PNG image content, resized to fit in a square.

    Original content is kept, the image is enlarged as necesary
    with transparent borders.
    """
    try:
        src_bytes = io.BytesIO(src)
        src_bytes.seek(0)
        img = Image.open(src_bytes).convert("RGBA")
        orig_size = img.size
        max_size = max(orig_size[0], orig_size[1])
        ratio = min(max_size / orig_size[0], max_size / orig_size[1])
        new_width = int(orig_size[0] * ratio)
        new_height = int(orig_size[1] * ratio)
        canvas = Image.new("RGBA", (max_size, max_size), (255, 255, 255, 0))
        x_offset = (max_size - new_width) // 2
        y_offset = (max_size - new_height) // 2
        canvas.paste(img, (x_offset, y_offset))
        with io.BytesIO() as dest_bytes:
            canvas.save(dest_bytes, format="PNG")
            return dest_bytes.getvalue()
    except (UnidentifiedImageError, OSError):
        return src
