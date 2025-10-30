# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for lib/image_utils module."""

from __future__ import annotations

import io

from PIL import Image

from app.lib.image_utils import resized, squared


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
