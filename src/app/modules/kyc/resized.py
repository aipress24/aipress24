# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

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
        size = (int(round(orig_size[0] * ratio)), int(round(orig_size[1] * ratio)))
        img = img.resize(size, Image.BICUBIC)
        with io.BytesIO() as dest_bytes:
            img.save(dest_bytes, format="JPEG", quality=95)
            return dest_bytes.getvalue()
    except (UnidentifiedImageError, OSError):
        return src
