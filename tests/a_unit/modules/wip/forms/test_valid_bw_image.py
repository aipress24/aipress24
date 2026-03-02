# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for wip/forms/business_wall/valid_bw_image.py."""

from __future__ import annotations

from unittest.mock import MagicMock

from wtforms import Form

from app.modules.wip.forms.business_wall.valid_bw_image import ValidBWImageField


class TestValidBWImageField:
    """Test ValidBWImageField."""

    def test_init_default_values(self):
        """Test default values are set correctly."""

        class TestForm(Form):
            image = ValidBWImageField()

        form = TestForm()
        assert form.image.max_image_size == 2048
        assert form.image.is_required is False
        assert form.image.readonly is False
        assert form.image.file_object is None
        assert form.image.multiple is False

    def test_init_custom_max_image_size(self):
        """Test custom max_image_size."""

        class TestForm(Form):
            image = ValidBWImageField(max_image_size=4096)

        form = TestForm()
        assert form.image.max_image_size == 4096

    def test_init_is_required(self):
        """Test is_required flag."""

        class TestForm(Form):
            image = ValidBWImageField(is_required=True)

        form = TestForm()
        assert form.image.is_required is True

    def test_init_readonly(self):
        """Test readonly flag."""

        class TestForm(Form):
            image = ValidBWImageField(readonly=True)

        form = TestForm()
        assert form.image.readonly is True

    def test_preload_filename_with_no_file_object(self):
        """Test preload_filename returns empty string when no file_object."""

        class TestForm(Form):
            image = ValidBWImageField()

        form = TestForm()
        assert form.image.preload_filename == ""

    def test_preload_filename_with_file_object(self):
        """Test preload_filename returns filename from file_object."""
        mock_file = MagicMock()
        mock_file.filename = "test.jpg"

        class TestForm(Form):
            image = ValidBWImageField(file_object=mock_file)

        form = TestForm()
        assert form.image.preload_filename == "test.jpg"

    def test_preload_filesize_with_no_file_object(self):
        """Test preload_filesize returns 0 when no file_object."""

        class TestForm(Form):
            image = ValidBWImageField()

        form = TestForm()
        assert form.image.preload_filesize == 0

    def test_preload_filesize_with_file_object(self):
        """Test preload_filesize returns size from file_object."""
        mock_file = MagicMock()
        mock_file.size = 1024

        class TestForm(Form):
            image = ValidBWImageField(file_object=mock_file)

        form = TestForm()
        assert form.image.preload_filesize == 1024

    def test_get_image_url_with_no_file_object(self):
        """Test get_image_url returns None when no file_object."""

        class TestForm(Form):
            image = ValidBWImageField()

        form = TestForm()
        assert form.image.get_image_url() is None

    def test_get_image_url_with_file_object(self):
        """Test get_image_url returns signed URL from file_object."""
        mock_file = MagicMock()
        mock_file.sign.return_value = "https://example.com/signed-url"

        class TestForm(Form):
            image = ValidBWImageField(file_object=mock_file)

        form = TestForm()
        assert form.image.get_image_url() == "https://example.com/signed-url"
        mock_file.sign.assert_called_once()

    def test_id_preload_name(self):
        """Test id_preload_name returns correct id suffix."""

        class TestForm(Form):
            image = ValidBWImageField()

        form = TestForm()
        assert form.image.id_preload_name() == "image_preload_name"

    def test_name_preload_name(self):
        """Test name_preload_name returns correct name suffix."""

        class TestForm(Form):
            image = ValidBWImageField()

        form = TestForm()
        assert form.image.name_preload_name() == "image_preload_name"
