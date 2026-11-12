# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""The sign-up wizard never stores a password as typed.

The wizard keeps its answers in `ses_session`, a plain JSON column that
every database export carries, so the password is hashed as soon as the
form is parsed.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from flask_security import verify_password
from flask_wtf import FlaskForm

from app.modules.kyc.lib.valid_password import ValidPassword
from app.modules.kyc.views import SESSION_HASH_KEY, _parse_result

if TYPE_CHECKING:
    from flask import Flask

SECRET = "correct horse battery staple"


class _PasswordForm(FlaskForm):
    password = ValidPassword()


def _parse(app: Flask, password: str) -> tuple[dict, dict]:
    form_results: dict = {}
    form_raw_results: dict = {"password": "left by an earlier version"}
    with app.test_request_context():
        form = _PasswordForm(data={"password": password}, meta={"csrf": False})
        _parse_result(form_results, form_raw_results, field=form.password)
    return form_results, form_raw_results


def test_only_a_hash_reaches_the_session(app: Flask) -> None:
    form_results, form_raw_results = _parse(app, f"  {SECRET} ")

    stored = json.dumps([form_results, form_raw_results])
    assert SECRET not in stored
    assert "left by an earlier version" not in stored
    with app.app_context():
        assert verify_password(SECRET, form_raw_results[SESSION_HASH_KEY])


def test_an_empty_password_is_not_hashed_into_a_valid_one(app: Flask) -> None:
    """`hash_password("")` yields a hash the empty password satisfies."""
    _form_results, form_raw_results = _parse(app, "   ")

    assert form_raw_results[SESSION_HASH_KEY] == ""
