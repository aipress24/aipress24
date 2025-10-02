# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import io

from PIL import Image, UnidentifiedImageError


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
