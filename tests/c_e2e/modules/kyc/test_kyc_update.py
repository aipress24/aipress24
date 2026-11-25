# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""KYC profile updates by a logged-in user, which commit."""

from __future__ import annotations

from flask import g, session as flask_session
from flask_security import login_user
from svcs.flask import container

from app.models.auth import KYCProfile, Role, User
from app.modules.kyc.populate_profile import populate_json_field
from app.modules.kyc.views import _update_current_user_data
from app.services.sessions import SessionService

PROFILE_JSON_FIELDS = (
    "info_personnelle",
    "info_professionnelle",
    "match_making",
    "info_hobby",
    "business_wall",
)


def test_logged_in_user_minor_kyc_update_is_applied(app, db_session, monkeypatch):
    monkeypatch.setattr(
        "app.modules.kyc.views.generate_roles_map",
        lambda: {"PRESS_MEDIA": Role(name="PRESS_MEDIA")},
    )
    user = User(
        email="kyc-update@example.com",
        gender="F",
        first_name="Ada",
        last_name="Lovelace",
    )
    # A profile that has been through the KYC, as `_clone_with_answers`
    # expects: every survey field present.
    user.profile = KYCProfile(
        **{name: populate_json_field(name, {}) for name in PROFILE_JSON_FIELDS}
    )
    db_session.add(user)
    db_session.flush()
    session_service = container.get(SessionService)

    with app.test_request_context():
        login_user(user)
        g.user = user
        flask_session["session_id"] = "test-kyc-update-session"
        session_service.set("profile_id", "P002")
        session_service.set(
            "form_raw_results",
            {
                # Same identity, so no moderator validation is needed.
                "civilite": "F",
                "first_name": "Ada",
                "last_name": "Lovelace",
                "tel_mobile": "0601020304",
            },
        )
        assert _update_current_user_data() == ""

    assert db_session.get(User, user.id).tel_mobile == "0601020304"
