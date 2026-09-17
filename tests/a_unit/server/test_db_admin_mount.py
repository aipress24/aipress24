# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""The /db/ console is not mounted unless asked for.

`adminapp.admin.create_admin` builds `Admin(app, engine, base_url="/db")`
with no `authentication_backend`, and sqladmin reads a missing backend as
"already authenticated". Mounted unconditionally — which it was, in the
process the Procfile starts — that served full read/write on users, KYC
profiles and editorial content to anonymous visitors.
"""

from __future__ import annotations

import server.main


def _mounted_paths(monkeypatch, **flags) -> set[str]:
    for name, value in flags.items():
        monkeypatch.setattr(server.main, name, value)
    monkeypatch.setattr(server.main, "create_flask_app", lambda: lambda *a: None)
    return {route.path for route in server.main.create_app().routes}


def test_db_admin_is_absent_by_default(monkeypatch):
    paths = _mounted_paths(monkeypatch, DB_ADMIN_ENABLED=False, POC_ENABLED=False)

    assert not any(p.startswith("/db") for p in paths), paths


def test_the_flask_app_is_still_served(monkeypatch):
    # Starlette normalises `Mount("/")` to the empty path.
    paths = _mounted_paths(monkeypatch, DB_ADMIN_ENABLED=False, POC_ENABLED=False)

    assert "" in paths


def test_the_default_is_off_not_merely_unset():
    """A missing environment variable must mean "not mounted", not
    "whatever the config object felt like"."""
    assert server.main.DB_ADMIN_ENABLED is False
