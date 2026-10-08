# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Per-module UI state must not survive a change of user.

Bug #0118 cleared `events:`, `wire:`, `swork:` and `biz:` at login.
`newsroom:` was set by two modules and cleared by none, so a shared
browser handed the next member the previous one's ciblage filters.

The test walks the source rather than listing keys by hand: a module
that invents a new prefix should fail here, not in production.
"""

from __future__ import annotations

import re
from pathlib import Path

from flask import session

from app.flask.hooks import (
    _PER_USER_SESSION_EXACT_KEYS,
    _PER_USER_SESSION_KEY_PREFIXES,
    _clear_per_user_session_state,
)

SRC = Path(__file__).resolve().parents[3] / "src" / "app"

# `"<module>:<something>"` string literals, which is how every module
# names its own session state.
_SESSION_KEY = re.compile(r'"([a-z_]+:)[a-z_]*"')

# Prefixes that are not per-user UI state and must not be cleared.
_NOT_UI_STATE = {"http:", "https:", "mailto:", "data:", "text:", "image:"}


def _prefixes_used_in_source() -> set[str]:
    found: set[str] = set()
    for path in SRC.rglob("*.py"):
        for prefix in _SESSION_KEY.findall(path.read_text(encoding="utf-8")):
            found.add(prefix)
    return found - _NOT_UI_STATE


def test_newsroom_state_is_cleared_at_login():
    assert "newsroom:" in _PER_USER_SESSION_KEY_PREFIXES


def test_bw_state_is_cleared_at_login():
    assert "bw:" in _PER_USER_SESSION_KEY_PREFIXES
    assert "bw_" in _PER_USER_SESSION_KEY_PREFIXES
    assert "suggested_bw_type" in _PER_USER_SESSION_EXACT_KEYS
    assert "contacts_confirmed" in _PER_USER_SESSION_EXACT_KEYS


def test_clear_per_user_session_state_drops_bw_and_module_keys(app):
    with app.test_request_context():
        session["bw_id"] = "11111111-1111-1111-1111-111111111111"
        session["bw_type"] = "pr"
        session["bw_activated"] = True
        session["suggested_bw_type"] = "media"
        session["events:state"] = "filtered"
        session["wire:tab"] = "my_tab"
        session["unrelated_system_key"] = "keep_me"

        _clear_per_user_session_state(app)

        assert "bw_id" not in session
        assert "bw_type" not in session
        assert "bw_activated" not in session
        assert "suggested_bw_type" not in session
        assert "events:state" not in session
        assert "wire:tab" not in session
        assert session.get("unrelated_system_key") == "keep_me"


def test_every_module_prefix_that_stores_state_is_cleared():
    """A prefix used by a module's session keys but absent here means
    that module's state outlives its owner."""
    module_prefixes = {
        p for p in _prefixes_used_in_source() if p.rstrip(":") in _KNOWN_MODULES
    }

    missing = module_prefixes - set(_PER_USER_SESSION_KEY_PREFIXES)

    assert not missing, f"state kept across users for: {sorted(missing)}"


_KNOWN_MODULES = {"events", "wire", "swork", "biz", "newsroom", "wip", "kyc"}
