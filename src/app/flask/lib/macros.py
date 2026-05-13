# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from collections.abc import Callable
from functools import wraps

from flask.app import Flask
from markupsafe import Markup

MACROS: list[Callable] = []


def macro(f: Callable) -> Callable:
    """Decorator: register `f` as a global Jinja template helper.

    Macros declared with this decorator return raw HTML built via
    `webbits.html.h` and friends — i.e. plain `str` values that happen
    to contain markup. With Jinja autoescape now enabled on `.j2`
    templates (see `app.flask.config`), a bare `str` returned by a
    macro is escaped at render and the tab bar / icon / table appears
    as visible angle brackets. Wrap every return value in `Markup` so
    the markup is treated as safe at the template layer — the same
    guarantee that the macros relied on under the old, lax autoescape
    policy.

    Macros that intentionally want to return escapable text can call
    `Markup.escape(...)` themselves before returning ; in practice
    every macro in this codebase builds HTML from server-controlled
    strings, not user input.
    """

    @wraps(f)
    def _wrapped(*args, **kwargs):
        result = f(*args, **kwargs)
        if result is None:
            return Markup("")
        return Markup(result) if not isinstance(result, Markup) else result

    MACROS.append(_wrapped)
    return _wrapped


def register_macros(app: Flask) -> None:
    for macro in MACROS:
        name = getattr(macro, "__name__", str(macro))
        app.template_global(name)(macro)
