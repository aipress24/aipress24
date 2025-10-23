# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for KYC validation field widgets."""

from __future__ import annotations

from wtforms import Form

from app.modules.kyc.lib.valid_email import ValidEmail
from app.modules.kyc.lib.valid_password import ValidPassword
from app.modules.kyc.lib.valid_tel import ValidTel
from app.modules.kyc.lib.valid_url import ValidURL


class TestForm(Form):
    """Test form to bind fields."""

    email = ValidEmail(label="Email")
    email_readonly = ValidEmail(label="Email", readonly=True)
    phone = ValidTel(label="Phone")
    phone_readonly = ValidTel(label="Phone", readonly=True)
    url = ValidURL(label="Website")
    url_readonly = ValidURL(label="Website", readonly=True)
    password = ValidPassword(label="Password")
    password_readonly = ValidPassword(label="Password", readonly=True)


def test_valid_email_init():
    """Test ValidEmail field initialization."""
    form = TestForm()
    assert form.email.name == "email"
    assert form.email.label.text == "Email"
    assert not form.email.readonly

    assert form.email_readonly.readonly


def test_valid_email_get_data():
    """Test ValidEmail get_data method."""
    form = TestForm(data={"email": "test@example.com"})
    assert form.email.get_data() == "test@example.com"

    # Test with None/empty
    form = TestForm(data={"email": None})
    assert form.email.get_data() == ""


def test_valid_tel_init():
    """Test ValidTel field initialization."""
    form = TestForm()
    assert form.phone.name == "phone"
    assert form.phone.label.text == "Phone"
    assert not form.phone.readonly

    assert form.phone_readonly.readonly


def test_valid_tel_get_data():
    """Test ValidTel get_data method."""
    form = TestForm(data={"phone": "+33 1 23 45 67 89"})
    assert form.phone.get_data() == repr("+33 1 23 45 67 89")

    # Test with None/empty
    form = TestForm(data={"phone": None})
    assert form.phone.get_data() == repr("")


def test_valid_url_init():
    """Test ValidURL field initialization."""
    form = TestForm()
    assert form.url.name == "url"
    assert form.url.label.text == "Website"
    assert not form.url.readonly

    assert form.url_readonly.readonly


def test_valid_url_get_data():
    """Test ValidURL get_data method."""
    form = TestForm(data={"url": "https://example.com"})
    assert form.url.get_data() == "https://example.com"

    # Test with None/empty
    form = TestForm(data={"url": None})
    assert form.url.get_data() == ""


def test_valid_password_init():
    """Test ValidPassword field initialization."""
    form = TestForm()
    assert form.password.name == "password"
    assert form.password.label.text == "Password"
    assert not form.password.readonly

    assert form.password_readonly.readonly


def test_valid_password_get_data():
    """Test ValidPassword get_data method."""
    form = TestForm(data={"password": "secret123"})
    assert form.password.get_data() == "secret123"

    # Test with None/empty
    form = TestForm(data={"password": None})
    assert form.password.get_data() == ""
