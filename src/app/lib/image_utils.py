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

    Priority : ``data_url`` BEFORE ``file_storage``. The two fields
    co-exist in the cropper.js form pattern : the visible
    ``<input type="file">`` carries the user's original upload as
    a FileStorage, and a separate hidden ``<input name="image">``
    carries the cropped image as a base64 data-URL once the user
    has clicked « Valider le cadrage ». Preferring the data_url
    means the user's CROPPED image is what gets saved (vs. the
    pre-crop original) — ref bug #0121. If the cropper wasn't
    used (data_url empty), we fall back to the file_storage as-is.

    Args:
        file_storage: FileStorage from request.files
        data_url: Base64 data URL from request.form
        orig_filename: Filename of orig image (for cropped images)

    Returns:
        UploadedImageData or None if no image found
    """
    # 1) Cropper-generated data-URL takes precedence : if the user
    # cropped the image, this carries the cropped result. The
    # `file_storage` is the *original* upload that we should
    # ignore in this case.
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
            # Malformed data-URL : fall through to the file
            # storage rather than dropping the upload entirely.
            pass

    # 2) Plain file upload (cropper not used, or its data-URL was
    # malformed).
    if file_storage is not None:
        image_bytes = file_storage.read()
        if image_bytes:
            return UploadedImageData(
                bytes=image_bytes,
                filename=file_storage.filename or "image.jpg",
                content_type=file_storage.content_type or "application/octet-stream",
            )

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
        # Validate integrity before processing. Weasyprint (imported elsewhere
        # in the app) sets PIL.ImageFile.LOAD_TRUNCATED_IMAGES globally, which
        # makes Image.open/convert silently accept truncated PNGs; verify()
        # still raises on them.
        Image.open(io.BytesIO(src)).verify()
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
