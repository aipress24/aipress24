# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""`ACCEPT_ANY_PASSWORD`, the end-to-end login bypass.

The flag exists so the Playwright suite can log in against a restored
database whose password hashes do not match the CSV fixtures. It makes
`User.verify_and_update_password` return `True` for anything, which is
about as dangerous as a switch gets — so what is pinned here is not
only that it works, but that it stays off unless deliberately turned
on, and that it cannot be turned on by itself.

`_install_password_bypass` patches the class, so every test that turns
it on must restore the original method — `restore_method` does.
"""

from __future__ import annotations

import pytest
from flask_security import hash_password

from app.flask.extensions import _install_password_bypass
from app.models.auth import User

REAL_PASSWORD = "the-actual-password"


@pytest.fixture
def restore_config(app):
    """Put `UNSECURE` and the flag back: `app` is session-scoped.

    `tests/conftest.py` turns `UNSECURE` on for the whole session so the
    backdoor routes work; a test that left it off would break whichever
    backdoor test happened to run next.
    """
    keys = ("ACCEPT_ANY_PASSWORD", "UNSECURE")
    saved = {k: app.config.get(k) for k in keys}
    yield app.config
    for key, value in saved.items():
        if value is None:
            app.config.pop(key, None)
        else:
            app.config[key] = value


@pytest.fixture
def restore_method():
    """Put the real `verify_and_update_password` back on the class."""
    original = User.verify_and_update_password
    yield
    User.verify_and_update_password = original


@pytest.fixture
def user(db) -> User:
    """A user whose password hash is real, not a placeholder."""
    with_hash = User(
        email="bypass@example.com",
        first_name="B",
        last_name="P",
        active=True,
        password=hash_password(REAL_PASSWORD),
    )
    db.session.add(with_hash)
    db.session.flush()
    return with_hash


def test_the_right_password_is_accepted(app, user: User) -> None:
    """The baseline: without the flag, verification is real."""
    assert user.verify_and_update_password(REAL_PASSWORD) is True


def test_a_wrong_password_is_refused_by_default(app, user: User) -> None:
    """Nothing about this change may weaken the default path."""
    assert not user.verify_and_update_password("not-the-password")


def test_the_flag_is_off_unless_it_is_set(app) -> None:
    """A test suite that silently ran with the bypass on would be lying."""
    assert not app.config.get("ACCEPT_ANY_PASSWORD")


def test_any_password_is_accepted_when_the_flag_is_on(
    app, restore_config, restore_method, user: User
) -> None:
    restore_config["ACCEPT_ANY_PASSWORD"] = True
    restore_config["UNSECURE"] = True
    _install_password_bypass(app)

    assert user.verify_and_update_password("nonsense") is True
    assert user.verify_and_update_password("") is True


def test_startup_refuses_the_flag_without_unsecure(app, restore_config) -> None:
    """One variable must not be enough to open every account.

    `UNSECURE` is the switch the `/backdoor/` routes already stand
    behind, so a deployment that has it set is one that has already
    declared itself not to be production.
    """
    restore_config["ACCEPT_ANY_PASSWORD"] = True
    restore_config["UNSECURE"] = False

    with pytest.raises(RuntimeError, match="ACCEPT_ANY_PASSWORD"):
        _install_password_bypass(app)


def test_startup_allows_the_flag_alongside_unsecure(
    app, restore_config, restore_method
) -> None:
    restore_config["ACCEPT_ANY_PASSWORD"] = True
    restore_config["UNSECURE"] = True

    _install_password_bypass(app)  # must not raise


def test_startup_is_silent_when_the_flag_is_absent(app, restore_config) -> None:
    restore_config["UNSECURE"] = False

    _install_password_bypass(app)  # must not raise
