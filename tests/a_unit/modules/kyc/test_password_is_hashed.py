# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""The sign-up wizard must never store a password as typed.

`User.password` is a plain column — no setter, no listener — and the
only `hash_password` calls in the tree were the CLI and the faker. The
wizard's own comment said "to be hashed by bcrypt"; nothing did, so the
applicant's password sat in the table in clear and the account could
not authenticate either.
"""

from __future__ import annotations

import inspect

from flask_security import hash_password, verify_password

from app.modules.kyc import views

SECRET = "correct horse battery staple"


def test_the_wizard_hashes_before_storing(app):
    with app.app_context():
        stored = hash_password(SECRET)

    assert stored != SECRET
    assert verify_password(SECRET, stored)


def test_the_creation_site_does_not_pass_the_raw_value():
    """Reading the source rather than the database: the defect was a
    single argument, and it is the argument we must keep honest."""
    source = inspect.getsource(views)

    assert 'password=results.get("password"' not in source
    assert "password=hash_password(" in source


def test_an_empty_password_is_not_hashed_into_a_valid_one():
    """`hash_password("")` yields a hash the empty password satisfies —
    an account anyone can open. Empty must stay empty."""
    source = inspect.getsource(views)

    assert "if submitted_password else None" in source
