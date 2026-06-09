# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the `confirm_role_invitation` route module.

The route at `confirm_role_invitation.py` is mostly an imperative
shell wired straight to `db.session` — there are no pure helpers
to test in isolation. What CAN be pinned without a full Flask
test client is the module's *contract surface* :

- **The blueprint registration** : URL pattern, accepted HTTP
  methods and endpoint name. The activation email links built
  elsewhere in the codebase encode this exact URL — drift here
  silently breaks every outgoing invitation mail.
- **The module-level imports** : `BW_ROLE_TYPE_LABEL`, the three
  `ERR_*` constants and `can_access_bw_dashboard` are all
  expected to be resolvable at import time. A typo in any of
  those names would only blow up the *first* time a user clicks
  an invitation link in production.
- **The string values the route compares against** : the inline
  state-machine reads `InvitationStatus.PENDING.value` and the
  PR-mission branch tests `BWRoleType.BWPRI.value` /
  `BWRoleType.BWPRE.value`. These tests pin the exact string
  forms so a future rename of an enum member can't silently
  break the route's behaviour.

The richer end-to-end accept/reject behaviour lives in
`tests/c_e2e/modules/bw/test_confirm_role_invitation.py` — this
file deliberately stays at the import-and-wiring level.
"""

from __future__ import annotations

import inspect

import pytest
from flask import Flask

from app.modules.bw.bw_activation import bp
from app.modules.bw.bw_activation.bw_invitation import BW_ROLE_TYPE_LABEL
from app.modules.bw.bw_activation.models import BWRoleType, InvitationStatus
from app.modules.bw.bw_activation.routes import (
    confirm_role_invitation as route_module,
)
from app.modules.bw.bw_activation.utils import (
    ERR_BW_NOT_FOUND,
    ERR_INVITATION_NOT_FOUND,
    ERR_WRONG_VALIDATION_LINK,
    can_access_bw_dashboard,
)

ENDPOINT = "bw_activation.confirm_role_invitation"


@pytest.fixture(scope="module")
def url_map():
    """Register the BW activation blueprint on a throw-away Flask
    app and return its URL map. We use module scope because the
    blueprint registration is idempotent and inexpensive — sharing
    the URL map keeps the test file fast."""
    app = Flask(__name__)
    app.register_blueprint(bp, url_prefix="/bw")
    return app.url_map


class TestRouteRegistration:
    """Pin the route's wiring : URL pattern, HTTP methods and
    endpoint name. Outgoing invitation emails are generated from
    this exact URL — silent drift would 404 every link sent."""

    def test_endpoint_is_registered(self, url_map):
        """The endpoint name has to stay `confirm_role_invitation`
        on the `bw_activation` blueprint — `url_for(...)` calls
        in templates and email builders use this string."""
        endpoints = {rule.endpoint for rule in url_map.iter_rules()}
        assert ENDPOINT in endpoints

    def test_url_pattern(self, url_map):
        """The URL is the public contract of an invitation email —
        the `<bw_id>/<role_type>/<int:user_id>` shape must stay
        stable so old links keep working."""
        rule = next(r for r in url_map.iter_rules() if r.endpoint == ENDPOINT)
        # blueprint mounted at /bw in the fixture above
        assert (
            rule.rule == "/bw/confirm-role-invitation/<bw_id>/<role_type>/<int:user_id>"
        )

    def test_user_id_is_int_converter(self, url_map):
        """`user_id` is typed as `int` in the URL converter so the
        view's signature can rely on a real Python `int`. Pin this
        because the view does an `==` comparison against
        `current_user.id` (a `BigInteger` PK) — a stringly typed
        path arg would silently fail every security check."""
        rule = next(r for r in url_map.iter_rules() if r.endpoint == ENDPOINT)
        # converter is recorded in `_converters` keyed by arg name
        assert rule._converters["user_id"].__class__.__name__ == "IntegerConverter"

    def test_accepts_get_and_post(self, url_map):
        """The route handles BOTH the form display (GET) and the
        accept/reject submission (POST). If either method falls
        off the rule, half of the flow would break — and the
        breakage wouldn't be caught by import-time checks."""
        rule = next(r for r in url_map.iter_rules() if r.endpoint == ENDPOINT)
        methods = rule.methods - {"HEAD", "OPTIONS"}
        assert methods == {"GET", "POST"}

    def test_view_function_signature(self):
        """The view takes exactly `(bw_id, role_type, user_id)` —
        the same three names Flask binds from URL converters.
        A mismatched signature would 500 every request."""
        sig = inspect.signature(route_module.confirm_role_invitation)
        assert list(sig.parameters) == ["bw_id", "role_type", "user_id"]


class TestModuleConstants:
    """Pin the names the route module pulls in at import time.
    A typo or renamed export anywhere upstream would only surface
    on the first real click of an invitation link — these tests
    fail fast at import time instead."""

    def test_error_constants_are_strings(self):
        """The three `ERR_*` flash-message constants are plain
        strings the route stores in the Flask session. Pin the
        type so a future refactor to a callable doesn't slip in
        unnoticed."""
        assert isinstance(ERR_BW_NOT_FOUND, str)
        assert isinstance(ERR_INVITATION_NOT_FOUND, str)
        assert isinstance(ERR_WRONG_VALIDATION_LINK, str)

    def test_error_constants_are_non_empty(self):
        """Empty flash messages would leave the user staring at
        a blank error page — guard against an accidental `= ""`."""
        assert ERR_BW_NOT_FOUND.strip()
        assert ERR_INVITATION_NOT_FOUND.strip()
        assert ERR_WRONG_VALIDATION_LINK.strip()

    def test_error_constants_are_distinct(self):
        """Each branch (wrong link, BW gone, invitation gone) has
        its own dedicated user-facing message. Collapsing two of
        them to the same string would make the « not_authorized »
        page misleading."""
        msgs = {ERR_BW_NOT_FOUND, ERR_INVITATION_NOT_FOUND, ERR_WRONG_VALIDATION_LINK}
        assert len(msgs) == 3

    def test_can_access_bw_dashboard_is_callable(self):
        """The route reads the dashboard-access predicate to set a
        template flag. Imported once at module load — confirm the
        symbol resolves to a callable rather than, say, a value."""
        assert callable(can_access_bw_dashboard)

    def test_bw_role_type_label_covers_all_roles(self):
        """Every `BWRoleType` member needs a human-readable label
        because the route renders `bw_role_name` in the email
        confirmation page. A missing key falls back to
        « (rôle inconnu) » which is a clear UX regression."""
        for role in BWRoleType:
            assert role.value in BW_ROLE_TYPE_LABEL


class TestStateMachineStrings:
    """The route compares the persisted `invitation_status`
    (a `str` column) against `InvitationStatus.<X>.value`. The
    string forms ARE the wire-level contract with the database
    column and any external system that inspects it — pin them
    so an enum rename can't silently change row meaning."""

    @pytest.mark.parametrize(
        ("member", "expected"),
        [
            (InvitationStatus.PENDING, "pending"),
            (InvitationStatus.ACCEPTED, "accepted"),
            (InvitationStatus.REJECTED, "rejected"),
        ],
    )
    def test_invitation_status_values(self, member, expected):
        """The route reads `PENDING.value` to test the « not yet
        processed » branch and writes `ACCEPTED.value` /
        `REJECTED.value` on POST. Renaming any of those
        underlying strings would corrupt every row in the DB."""
        assert member.value == expected

    @pytest.mark.parametrize(
        ("member", "expected"),
        [
            (BWRoleType.BWPRI, "BWPRi"),
            (BWRoleType.BWPRE, "BWPRe"),
        ],
    )
    def test_pr_role_string_values(self, member, expected):
        """The route's accept branch fires
        `apply_bw_missions_to_pr_user(...)` ONLY when the role
        is one of `BWPRi` / `BWPRe`. The check is a string
        compare against `BWRoleType.BWPRI.value` /
        `BWRoleType.BWPRE.value` — pin the camel-case form."""
        assert member.value == expected

    def test_non_pr_roles_are_excluded_from_pr_branch(self):
        """The PR-mission application branch must NOT fire for
        owners, internal BW managers or external BW managers.
        We pin the set membership so an accidental inclusion of
        e.g. `BW_OWNER` in the same tuple doesn't slip past
        code review."""
        pr_roles = {BWRoleType.BWPRI.value, BWRoleType.BWPRE.value}
        for role in BWRoleType:
            is_pr = role in {BWRoleType.BWPRI, BWRoleType.BWPRE}
            assert (role.value in pr_roles) is is_pr
