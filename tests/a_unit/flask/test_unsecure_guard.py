# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""`UNSECURE` must not survive into the production environment.

It opens `/backdoor/<role>` — one anonymous GET returning a session for
any role, ADMIN included — and `/debug/env`, which prints every secret
the process holds. It ships `true` in `[default]`, so every environment
inherited it; `[production]` now sets it false and this guard refuses to
start if it is ever seen there anyway.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flask import Flask

from app.flask.extensions import _refuse_or_announce_unsecure


def _app(**config) -> Flask:
    app = Flask(__name__)
    app.config.update(config)
    return app


def test_production_with_the_flag_refuses_to_start():
    app = _app(UNSECURE=True, ENV_FOR_DYNACONF="production")

    with pytest.raises(RuntimeError, match="UNSECURE"):
        _refuse_or_announce_unsecure(app)


def test_the_check_is_case_insensitive():
    """Dynaconf does not promise the case of the env name."""
    app = _app(UNSECURE=True, ENV_FOR_DYNACONF="PRODUCTION")

    with pytest.raises(RuntimeError):
        _refuse_or_announce_unsecure(app)


def test_development_with_the_flag_is_allowed(capsys):
    """Legitimate — and announced on stderr, so a server booting this
    way by mistake says so in its logs."""
    app = _app(UNSECURE=True, ENV_FOR_DYNACONF="development")

    _refuse_or_announce_unsecure(app)

    assert "UNSECURE is ON" in capsys.readouterr().err


def test_the_flag_off_says_nothing(capsys):
    app = _app(UNSECURE=False, ENV_FOR_DYNACONF="production")

    _refuse_or_announce_unsecure(app)

    assert capsys.readouterr().err == ""


def test_production_settings_turn_it_off():
    """The guard is a backstop; the settings are the actual fix."""
    settings = Path("etc/settings.toml").read_text()
    production = settings[settings.index("[production]") :]

    assert "UNSECURE = false" in production
