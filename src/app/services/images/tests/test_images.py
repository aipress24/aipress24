# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from pathlib import Path

from PIL import Image

from app.services.images import ImageService

IMAGE_PATH = Path(__file__).parent / "logo.png"


def test_make_square() -> None:
    img = Image.open(IMAGE_PATH)
    assert img

    image_service = ImageService()
    assert image_service

    new_img = image_service.make_square(img, 256)
    assert new_img.size == (256, 256)
