# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for flask/lib/proxies.py"""

from __future__ import annotations

from werkzeug.local import LocalProxy

from app.flask.lib.proxies import unproxy


def test_unproxy_returns_non_proxy_unchanged() -> None:
    """Test returns non-proxy objects unchanged."""
    obj = {"key": "value"}
    assert unproxy(obj) is obj
    assert unproxy("string") == "string"
    assert unproxy(None) is None


def test_unproxy_unwraps_local_proxy() -> None:
    """Test unwraps LocalProxy to get underlying object."""
    original = {"key": "value"}
    proxy = LocalProxy(lambda: original)

    assert unproxy(proxy) is original
