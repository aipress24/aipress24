# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for lib/image_utils module."""

from __future__ import annotations

import base64
import io

from PIL import Image

from app.lib.image_utils import (
    extract_image_from_request,
    resized,
    squared,
)


class TestResized:
    """Test suite for resized function."""

    def test_resize_large_image(self):
        """Test resizing a large image."""
        # Create a 1000x1000 image
        img = Image.new("RGB", (1000, 1000), color="red")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="JPEG")
        src = img_bytes.getvalue()

        result = resized(src, max_size=500)

        # Should be resized
        assert result != src
        # Check result is valid JPEG
        result_img = Image.open(io.BytesIO(result))
        assert result_img.size == (500, 500)

    def test_resize_wide_image(self):
        """Test resizing a wide image."""
        # Create a 1200x600 image
        img = Image.new("RGB", (1200, 600), color="blue")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="JPEG")
        src = img_bytes.getvalue()

        result = resized(src, max_size=800)

        # Should be resized to fit within 800
        result_img = Image.open(io.BytesIO(result))
        assert result_img.size[0] <= 800
        assert result_img.size[1] <= 800
        # Aspect ratio should be preserved
        assert abs(result_img.size[0] / result_img.size[1] - 2.0) < 0.01

    def test_resize_tall_image(self):
        """Test resizing a tall image."""
        # Create a 400x1000 image
        img = Image.new("RGB", (400, 1000), color="green")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="JPEG")
        src = img_bytes.getvalue()

        result = resized(src, max_size=500)

        # Should be resized
        result_img = Image.open(io.BytesIO(result))
        assert result_img.size[0] <= 500
        assert result_img.size[1] <= 500
        # Aspect ratio should be preserved (2.5:1)
        assert abs(result_img.size[1] / result_img.size[0] - 2.5) < 0.01

    def test_no_resize_small_image(self):
        """Test that small images are not resized."""
        # Create a 400x400 image
        img = Image.new("RGB", (400, 400), color="yellow")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="JPEG")
        src = img_bytes.getvalue()

        result = resized(src, max_size=800)

        # Should not be resized (ratio > 1.0)
        assert result == src

    def test_invalid_image_data(self):
        """Test with invalid image data."""
        src = b"not an image"
        result = resized(src)

        # Should return original bytes on error
        assert result == src

    def test_corrupted_image_data(self):
        """Test with corrupted image data."""
        # Create valid image header but truncate it
        img = Image.new("RGB", (100, 100), color="white")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="JPEG")
        src = img_bytes.getvalue()[:50]  # Truncate

        result = resized(src)

        # Should return original bytes on error
        assert result == src

    def test_custom_max_size(self):
        """Test with custom max_size parameter."""
        # Create a 2000x2000 image
        img = Image.new("RGB", (2000, 2000), color="purple")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="JPEG")
        src = img_bytes.getvalue()

        result = resized(src, max_size=1000)

        result_img = Image.open(io.BytesIO(result))
        assert result_img.size == (1000, 1000)


class TestSquared:
    """Test suite for squared function."""

    def test_square_wide_image(self):
        """Test making a wide image square."""
        # Create a 400x200 image
        img = Image.new("RGB", (400, 200), color="red")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        src = img_bytes.getvalue()

        result = squared(src)

        # Should be squared
        assert result != src
        result_img = Image.open(io.BytesIO(result))
        assert result_img.size == (400, 400)
        assert result_img.mode == "RGBA"

    def test_square_tall_image(self):
        """Test making a tall image square."""
        # Create a 200x400 image
        img = Image.new("RGB", (200, 400), color="blue")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        src = img_bytes.getvalue()

        result = squared(src)

        result_img = Image.open(io.BytesIO(result))
        assert result_img.size == (400, 400)
        assert result_img.mode == "RGBA"

    def test_square_already_square_image(self):
        """Test with an image that's already square."""
        # Create a 300x300 image
        img = Image.new("RGB", (300, 300), color="green")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        src = img_bytes.getvalue()

        result = squared(src)

        # Should still process it
        result_img = Image.open(io.BytesIO(result))
        assert result_img.size == (300, 300)
        assert result_img.mode == "RGBA"

    def test_square_with_rgba_input(self):
        """Test with RGBA input image."""
        # Create an RGBA image
        img = Image.new("RGBA", (300, 200), color=(255, 0, 0, 128))
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        src = img_bytes.getvalue()

        result = squared(src)

        result_img = Image.open(io.BytesIO(result))
        assert result_img.size == (300, 300)
        assert result_img.mode == "RGBA"

    def test_square_invalid_image_data(self):
        """Test squared with invalid image data."""
        src = b"not an image"
        result = squared(src)

        # Should return original bytes on error
        assert result == src

    def test_square_corrupted_image_data(self):
        """Test squared with corrupted image data."""
        # Create valid image header but truncate it
        img = Image.new("RGB", (100, 100), color="white")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        src = img_bytes.getvalue()[:50]  # Truncate

        result = squared(src)

        # Should return original bytes on error
        assert result == src

    def test_square_transparent_borders(self):
        """Test that borders are transparent."""
        # Create a wide image
        img = Image.new("RGB", (400, 200), color=(255, 0, 0))
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        src = img_bytes.getvalue()

        result = squared(src)

        result_img = Image.open(io.BytesIO(result))
        # Check top-left corner pixel (should be transparent)
        pixel = result_img.getpixel((0, 0))
        # Last component is alpha - should be 0 (fully transparent)
        assert pixel[3] == 0

        # Check middle pixel (should be red, opaque)
        center_pixel = result_img.getpixel((200, 200))
        assert center_pixel[0] == 255  # Red
        assert center_pixel[3] == 255  # Opaque


# Helpers for the cropper.js priority tests below.


class _StubFileStorage:
    """Minimal FileStorage stand-in for unit tests : just exposes
    `read()`, `filename`, `content_type` like the Werkzeug type."""

    def __init__(self, content: bytes, filename: str, content_type: str) -> None:
        self._content = content
        self.filename = filename
        self.content_type = content_type

    def read(self) -> bytes:
        return self._content


def _png_data_url() -> str:
    """Return a valid `data:image/png;base64,…` URL of a 1×1 red
    pixel — small but well-formed enough to round-trip through
    `extract_image_from_request`."""
    img = Image.new("RGB", (1, 1), color="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


class TestExtractImageFromRequest:
    """Test suite for extract_image_from_request — pin the
    cropper-data-URL-takes-precedence invariant (bug #0121)."""

    def test_returns_none_when_both_inputs_empty(self):
        """No file_storage AND no data_url → None."""
        assert extract_image_from_request() is None

    def test_returns_none_for_empty_file_storage(self):
        """A FileStorage that reads to empty bytes → None."""
        empty = _StubFileStorage(b"", "x.png", "image/png")
        assert extract_image_from_request(file_storage=empty) is None

    def test_returns_file_when_only_file_storage_provided(self):
        """Cropper not used : the upload is the only signal."""
        fs = _StubFileStorage(b"\x89PNGoriginal", "shot.png", "image/png")
        result = extract_image_from_request(file_storage=fs)
        assert result is not None
        assert result.bytes == b"\x89PNGoriginal"
        assert result.filename == "shot.png"
        assert result.content_type == "image/png"

    def test_returns_data_url_when_only_data_url_provided(self):
        """User cropped without an active file upload : data-URL
        is the sole signal."""
        result = extract_image_from_request(data_url=_png_data_url())
        assert result is not None
        assert result.content_type == "image/png"
        # Tiny 1×1 PNG → bytes len > 0.
        assert len(result.bytes) > 0

    def test_data_url_takes_precedence_over_file_storage(self):
        """REGRESSION : bug #0121.

        When the user picks a file (`file_storage`) AND uses
        the cropper to crop it (`data_url` filled with the
        cropped bytes), the function MUST return the cropped
        version. Before the fix, the original was returned and
        the user's crop was silently discarded.
        """
        fs = _StubFileStorage(
            b"ORIGINAL_BYTES_NOT_CROPPED",
            "shot.png",
            "image/png",
        )
        result = extract_image_from_request(
            file_storage=fs,
            data_url=_png_data_url(),
        )
        assert result is not None
        # The crop was returned (≠ original).
        assert result.bytes != b"ORIGINAL_BYTES_NOT_CROPPED", (
            "cropper data-URL should override file_storage. "
            "If this fails, the priority in "
            "`extract_image_from_request` regressed — bug #0121 "
            "is back."
        )
        # `data_url` parsing yields content_type from the URL,
        # not the FileStorage's.
        assert result.content_type == "image/png"

    def test_falls_back_to_file_storage_on_malformed_data_url(self):
        """A garbage `data:image/...` payload (e.g. truncated
        base64) should NOT swallow the upload — fall back to
        the file storage so the user's image isn't lost."""
        fs = _StubFileStorage(b"GOOD_FILE_BYTES", "shot.png", "image/png")
        result = extract_image_from_request(
            file_storage=fs,
            data_url="data:image/png;base64,!!!not-base64!!!",
        )
        assert result is not None
        assert result.bytes == b"GOOD_FILE_BYTES"

    def test_data_url_uses_orig_filename_when_provided(self):
        """When `orig_filename` matches the data-URL's media
        type, the original filename is preserved — keeps
        gallery captions and S3 paths consistent."""
        result = extract_image_from_request(
            data_url=_png_data_url(),
            orig_filename="custom-crop.png",
        )
        assert result is not None
        assert result.filename == "custom-crop.png"

    def test_data_url_swaps_extension_when_orig_filename_mismatches(self):
        """If user uploaded `shot.jpg` then the cropper exported
        as PNG, the result keeps the base name but uses .png."""
        result = extract_image_from_request(
            data_url=_png_data_url(),
            orig_filename="shot.jpg",
        )
        assert result is not None
        assert result.filename == "shot.png"
