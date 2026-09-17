# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for KYC /modify access and registration security.

Protection against unauthorized form modification:
"""

from __future__ import annotations

import pytest
from flask import g, session as flask_session
from flask_security.core import AnonymousUser
from svcs.flask import container

from app.models.auth import Role
from app.modules.kyc.views import _make_new_kyc_user_record
from app.services.sessions import SessionService


@pytest.fixture
def csrf_client(app):
    """The suite disables CSRF, but `wizard.html` renders
    `form.csrf_token`, which does not exist when it is off — so the
    page could not be rendered under the default test config at all.
    That is why the 500 reached production unnoticed."""
    app.config["WTF_CSRF_ENABLED"] = True
    try:
        yield app.test_client()
    finally:
        app.config["WTF_CSRF_ENABLED"] = False


def test_anonymous_modify_without_session_redirects_to_login(csrf_client):
    """Anonymous visitor with no session is sent to login."""
    response = csrf_client.get("/kyc/modify")

    assert response.status_code == 302
    assert response.headers["Location"] == "/login?next=/kyc/modify"


def test_anonymous_modify_with_registration_session_redirects_to_wizard(
    csrf_client,
):
    """An anonymous user with active profile_id is redirected to its wizard."""
    csrf_client.get("/kyc/wizard/P002")
    response = csrf_client.get("/kyc/modify")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/kyc/wizard/P002")


def test_anonymous_validation_page_previous_button_targets_wizard(csrf_client):
    """On /kyc/validation, the previous button for an anonymous user sends to wizard."""
    csrf_client.get("/kyc/wizard/P002")

    response = csrf_client.get("/kyc/validation")
    assert response.status_code == 200
    body = response.data.decode()
    assert "window.location.href = '/kyc/wizard/P002'" in body
    assert "window.location.href = '/kyc/modify'" not in body


def test_anonymous_wizard_always_renders_email_and_password(app, csrf_client):
    """edge case if modify_form is somehow set in session, anonymous wizard check credentials."""
    # Start session on wizard
    csrf_client.get("/kyc/wizard/P002")

    # Manually inject modify_form = True into session service
    with csrf_client.session_transaction() as sess:
        sess_id = sess.get("session_id")

    assert sess_id
    session_service = container.get(SessionService)
    with app.test_request_context():
        g.user = AnonymousUser()
        flask_session["session_id"] = sess_id
        session_service.set("modify_form", True)

    # fetch again wizard
    response = csrf_client.get("/kyc/wizard/P002")
    assert response.status_code == 200
    body = response.data.decode()

    # Email and password fields must be present (mode_edition must be False for anonymous)
    assert 'name="email"' in body
    assert 'name="password"' in body


def test_make_new_kyc_user_record_requires_email_and_password(app, monkeypatch):
    """_make_new_kyc_user_record raises ValueError if email or password is empty."""
    monkeypatch.setattr(
        "app.modules.kyc.views.generate_roles_map",
        lambda: {"PRESS_MEDIA": Role(name="PRESS_MEDIA")},
    )

    session_service = container.get(SessionService)

    with app.test_request_context():
        g.user = AnonymousUser()
        flask_session["session_id"] = "test-new-user-kyc-session"
        session_service.set("profile_id", "P002")

        session_service.set("form_raw_results", {})
        with pytest.raises(ValueError, match="Email address is required"):
            _make_new_kyc_user_record()

        session_service.set("form_raw_results", {"email": "applicant@example.com"})
        with pytest.raises(ValueError, match="Password is required"):
            _make_new_kyc_user_record()

        session_service.set(
            "form_raw_results", {"email": "   ", "password": "valid_secret_password"}
        )
        with pytest.raises(ValueError, match="Email address is required"):
            _make_new_kyc_user_record()

        session_service.set(
            "form_raw_results",
            {"email": "applicant@example.com", "password": "valid_secret_password"},
        )
        user = _make_new_kyc_user_record()
        assert user.email == "applicant@example.com"
        assert user.password is not None
