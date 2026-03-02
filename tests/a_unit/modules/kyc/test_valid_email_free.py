# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for kyc/lib/valid_email_free.py."""

from __future__ import annotations

from wtforms import Form

from app.modules.kyc.lib.valid_email_free import ValidEmailFree, ValidEmailFreeWidget


class TestValidEmailFree:
    """Test ValidEmailFree field."""

    def test_init_default_readonly(self):
        """Test default readonly is False."""

        class TestForm(Form):
            email = ValidEmailFree()

        form = TestForm()
        assert form.email.readonly is False

    def test_init_readonly_true(self):
        """Test readonly can be set to True."""

        class TestForm(Form):
            email = ValidEmailFree(readonly=True)

        form = TestForm()
        assert form.email.readonly is True

    def test_get_data_returns_empty_for_none(self):
        """Test get_data returns empty string when data is None."""

        class TestForm(Form):
            email = ValidEmailFree()

        form = TestForm()
        form.email.data = None
        assert form.email.get_data() == ""

    def test_get_data_returns_data_when_set(self):
        """Test get_data returns the actual data when set."""

        class TestForm(Form):
            email = ValidEmailFree()

        form = TestForm(data={"email": "test@example.com"})
        assert form.email.get_data() == "test@example.com"

    def test_widget_type(self):
        """Test field uses ValidEmailFreeWidget."""

        class TestForm(Form):
            email = ValidEmailFree()

        form = TestForm()
        assert isinstance(form.email.widget, ValidEmailFreeWidget)
