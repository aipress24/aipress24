# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from unittest.mock import Mock

import pytest
from flask import Flask
from flask_login import LoginManager

from app.flask.doorman import Doorman, doorman as global_doorman

login_manager = LoginManager()

pytestmark = pytest.mark.skip()


@pytest.fixture(scope="session")
def app():
    """Create a minimal Flask app for testing the before_request hook."""
    app = Flask(__name__)
    login_manager.init_app(app)

    # Define some dummy routes for the test client to hit.
    @app.route("/")
    def index() -> str:
        return "Public Page"

    @app.route("/admin/")
    def admin_index() -> str:
        return "Admin Index"

    @app.route("/admin/settings")
    def admin_settings() -> str:
        return "Admin Settings"

    # This is the crucial part: we register the real doorman instance
    # with our test app's before_request handler.
    @app.before_request
    def before_request_security_check() -> None:
        global_doorman.check_access()

    return app


@pytest.fixture(scope="module")
def client(app):
    """A test client for the app."""
    return app.test_client()


# --- Mock User Objects ---


@pytest.fixture
def mock_anonymous_user():
    """A mock for a user who is not logged in."""
    user = Mock()
    user.is_authenticated = False
    return user


@pytest.fixture
def mock_authenticated_user():
    """A mock for an authenticated user."""
    user = Mock()
    user.is_authenticated = True
    return user


# --- Test Cases ---


def test_unprotected_route_is_accessible_by_everyone(
    client, mock_anonymous_user
) -> None:
    """
    GIVEN a Flask app with the doorman
    WHEN an anonymous user accesses a public route ('/')
    THEN the request should succeed with a 200 OK status.
    """
    # We don't need to patch current_user because by default it's anonymous.
    response = client.get("/")
    assert response.status_code == 200
    assert b"Public Page" in response.data


def test_anonymous_user_on_protected_route_is_unauthorized(
    client, mocker, mock_anonymous_user
) -> None:
    """
    GIVEN the doorman's '/admin/' rule is active
    WHEN an anonymous (not logged in) user tries to access '/admin/settings'
    THEN the request should be rejected with a 401 Unauthorized status.
    """

    # Patch the `current_user` that the doorman will see.
    # mocker.patch("login_manager", mock_anonymous_user)
    @login_manager.request_loader
    def load_user_from_request(request):
        return mock_anonymous_user

    response = client.get("/admin/settings")
    assert response.status_code == 401


def test_non_admin_user_on_protected_route_is_forbidden(
    client, mocker, mock_authenticated_user
) -> None:
    """
    GIVEN the doorman's '/admin/' rule is active
    WHEN a logged-in, non-admin user tries to access '/admin/settings'
    THEN the request should be rejected with a 403 Forbidden status.
    """

    @login_manager.request_loader
    def load_user_from_request(request):
        return mock_authenticated_user

    # Patch the role check to explicitly return False
    mocker.patch("app.services.roles.has_role", return_value=False)

    response = client.get("/admin/settings")
    assert response.status_code == 403


def test_admin_user_on_protected_route_is_allowed(
    client, mocker, mock_authenticated_user
) -> None:
    """
    GIVEN the doorman's '/admin/' rule is active
    WHEN a logged-in admin user tries to access '/admin/settings'
    THEN the request should succeed with a 200 OK status.
    """

    @login_manager.request_loader
    def load_user_from_request(request):
        return mock_authenticated_user

    # Patch the role check to explicitly return True for the 'ADMIN' role
    mocker.patch("app.flask.doorman.has_role", return_value=True)

    response = client.get("/admin/settings")
    assert response.status_code == 200
    assert b"Admin Settings" in response.data


def test_doorman_decorator_registers_rule() -> None:
    """
    GIVEN a new Doorman instance
    WHEN the @doorman.rule decorator is used
    THEN a new Rule object should be added to the doorman's rules list.
    """
    # Test the decorator mechanism in isolation
    local_doorman = Doorman()
    assert len(local_doorman.rules) == 0

    @local_doorman.rule(prefix="/api/")
    def check_api_access(user) -> bool:
        return True

    assert len(local_doorman.rules) == 1

    new_rule = local_doorman.rules[0]
    assert new_rule.prefix == "/api/"
    assert new_rule.is_allowed == check_api_access
