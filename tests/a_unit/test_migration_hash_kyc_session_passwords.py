# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""The migration leaves no sign-up password in clear in `ses_session`."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

MIGRATION = (
    Path(__file__).parents[2]
    / "migrations/versions/a3c9e5f1b7d2_hash_kyc_session_passwords.py"
)
SECRET = "correct horse battery staple"


def _scrub():
    spec = importlib.util.spec_from_file_location("migration", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.scrub


def _session(email: str) -> dict:
    return {
        "profile_id": "P002",
        "form_raw_results": {"email": email, "password": f" {SECRET} "},
    }


def _hasher(password: str) -> str:
    return f"hashed:{password}"


def test_unfinished_sign_up_keeps_a_hash() -> None:
    data = _scrub()(_session("new@example.com"), set(), _hasher)

    assert SECRET not in json.dumps(data).replace(f"hashed:{SECRET}", "")
    assert data["form_raw_results"]["password_hash"] == f"hashed:{SECRET}"
    assert data["profile_id"] == "P002"


def test_finished_sign_up_keeps_nothing() -> None:
    data = _scrub()(_session("Done@Example.com"), {"done@example.com"}, _hasher)

    assert SECRET not in json.dumps(data)
    assert "password_hash" not in data["form_raw_results"]


def test_rows_without_a_password_are_untouched() -> None:
    data = {"form_raw_results": {"email": "x@example.com"}, "modify_form": True}

    assert _scrub()(data, set(), _hasher) == data
