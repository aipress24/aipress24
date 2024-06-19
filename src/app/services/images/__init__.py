# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask_super.decorators import service
from PIL import Image

FILL_COLOR = (255, 255, 255, 0)


@service
class ImageService:
    def make_square(self, img: Image.Image, size: int) -> Image.Image:
        x0, y0 = img.size
        s0 = max(x0, y0)

        new_img = Image.new("RGBA", (s0, s0), FILL_COLOR)

        new_img.paste(img, (int((s0 - x0) / 2), int((s0 - y0) / 2)))
        return new_img.resize((size, size))


# def make_square(img: Image.Image, size: int) -> Image.Image:
#     frame = np.asarray(img)
#     new_frame = make_square_cv2(frame)
#     new_image = Image.fromarray(new_frame)
#     return new_image.resize((size, size))
#
#
# def make_square_cv2(frame: np.ndarray) -> np.ndarray:
#     # x0, y0, s0 = dimensions of orig image
#     y0, x0 = frame.shape[0:2]
#     s0 = max(x0, y0)
#
#     # Creating a white square with Numpy
#     new_frame = np.zeros((s0, s0, 3), np.uint8)
#     new_frame[:] = (255, 255, 255)
#
#     # Getting the centering position
#     ax, ay = (s0 - x0) // 2, (s0 - y0) // 2
#     x1, y1, x2, y2 = ax, ay, x0 + ax, y0 + ay
#
#     new_frame[y1:y2, x1:x2] = (
#         new_frame[y1:y2, x1:x2] * (1 - frame[:, :, 3:] / 255)
#         #
#         + frame[:, :, :3] * (frame[:, :, 3:] / 255)
#     )
#     return new_frame
