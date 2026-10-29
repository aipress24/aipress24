# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""`UNSECURE` must only ever be honoured in debug or testing mode.

It opens `/backdoor/<role>` — one anonymous GET returning a session for
any role, ADMIN included — and `/debug/env`, which prints every secret
the process holds. A server that sets no `ENV_FOR_DYNACONF` resolves to
`[development]`, so the guard cannot key on the environment name.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from flask import Flask

from app.flask.extensions import _refuse_or_announce_unsecure


def _app(**config) -> Flask:
    app = Flask(__name__)
    app.config.update(config)
    return app


def test_the_flag_outside_debug_and_testing_refuses_to_start():
    app = _app(UNSECURE=True, DEBUG=False, TESTING=False)

    with pytest.raises(RuntimeError, match="UNSECURE"):
        _refuse_or_announce_unsecure(app)


def test_development_environment_name_does_not_open_the_gate():
    """What production did: no ENV_FOR_DYNACONF, so `[development]`."""
    app = _app(UNSECURE=True, ENV_FOR_DYNACONF="development", DEBUG=False)

    with pytest.raises(RuntimeError):
        _refuse_or_announce_unsecure(app)


@pytest.mark.parametrize("mode", ["DEBUG", "TESTING"])
def test_debug_or_testing_with_the_flag_is_allowed(mode, capsys):
    """Legitimate — and announced on stderr."""
    app = _app(UNSECURE=True, **{mode: True})

    _refuse_or_announce_unsecure(app)

    assert "UNSECURE is ON" in capsys.readouterr().err


def test_the_flag_off_says_nothing(capsys):
    app = _app(UNSECURE=False, DEBUG=False)

    _refuse_or_announce_unsecure(app)

    assert capsys.readouterr().err == ""


def test_no_settings_environment_turns_it_on():
    """The flag is opt-in through `FLASK_UNSECURE`, never shipped on."""
    settings = tomllib.loads(Path("etc/settings.toml").read_text())

    for name, section in settings.items():
        assert section.get("UNSECURE", False) is False, name
