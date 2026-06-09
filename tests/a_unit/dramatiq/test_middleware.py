# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `AppContextMiddleware`.

Every actor body needs a Flask app context to touch `current_app`,
`db.session`, `svcs.flask.container`, etc. The worker process doesn't
have one by default — `AppContextMiddleware.before_process_message`
pushes one before each message and pops it after, mirroring what
Flask does for a normal request.

These tests pin the lifecycle :
- before → app context is active,
- after_process_message → context is popped,
- after_skip_message → same path as after_process_message,
- after_process_message with `exception` → context is still popped,
- no leak across calls (state.context is cleaned up).
"""

from __future__ import annotations

from flask import Flask, current_app

from app.dramatiq.middleware import AppContextMiddleware

# The test session already has an autouse `db_session` fixture that
# pushes the *project's* app context (see tests/conftest.py:248). So
# we can't assert on `has_app_context()` — there's always one. Instead
# we assert that *our* dramatiq app becomes the active `current_app`
# while the middleware is mid-message, and that it's gone afterward.


def _active_app() -> Flask | None:
    """Return the currently-active Flask app, or None if no context."""
    try:
        return current_app._get_current_object()  # type: ignore[no-any-return]
    except RuntimeError:
        return None


class TestBeforeProcessMessage:
    def test_pushes_our_app_to_the_top_of_the_stack(self):
        """After `before_process_message`, `current_app` resolves to
        the dramatiq app — even if another app context was already
        active above us (the worker's web app, the test session, …)."""
        app = Flask("test-dramatiq-mw")
        mw = AppContextMiddleware(app)
        outer_app = _active_app()
        assert outer_app is not app  # sanity — sessions differ

        mw.before_process_message(broker=None, message=None)
        try:
            assert _active_app() is app
        finally:
            mw.after_process_message(broker=None, message=None)


class TestAfterProcessMessage:
    def test_pops_our_app_off_the_stack(self):
        app = Flask("test-dramatiq-mw")
        mw = AppContextMiddleware(app)
        outer_app = _active_app()
        mw.before_process_message(broker=None, message=None)
        assert _active_app() is app

        mw.after_process_message(broker=None, message=None)

        # Whatever was active before is active again.
        assert _active_app() is outer_app

    def test_pops_context_even_when_exception_arg_set(self):
        """`dramatiq` calls this with `exception=` set when the actor
        body raised. The context still needs popping so the worker
        doesn't leak a stack of contexts."""
        app = Flask("test-dramatiq-mw")
        mw = AppContextMiddleware(app)
        outer_app = _active_app()
        mw.before_process_message(broker=None, message=None)

        mw.after_process_message(
            broker=None, message=None, exception=RuntimeError("boom")
        )

        assert _active_app() is outer_app

    def test_tolerates_missing_before_call(self):
        """If `after_process_message` fires without a prior
        `before_process_message` (rare but possible during worker
        shutdown races), the AttributeError on `self.state.context`
        is swallowed — the worker must keep running."""
        app = Flask("test-dramatiq-mw")
        mw = AppContextMiddleware(app)

        # Should not raise.
        mw.after_process_message(broker=None, message=None)


class TestAfterSkipMessage:
    def test_is_same_as_after_process_message(self):
        """`after_skip_message = after_process_message` is the
        documented dramatiq pattern — skipped messages still need
        the context popped if before-message ever ran."""
        assert (
            AppContextMiddleware.after_skip_message
            is AppContextMiddleware.after_process_message
        )


class TestNoCrossMessageLeak:
    def test_two_consecutive_messages_keep_lifecycle_clean(self):
        """Sanity : push/pop twice in a row leaves no residue. Catches
        the kind of bug where the `local()` thread-local accidentally
        accumulates contexts across messages."""
        app = Flask("test-dramatiq-mw")
        mw = AppContextMiddleware(app)
        outer_app = _active_app()

        for _ in range(2):
            mw.before_process_message(broker=None, message=None)
            assert _active_app() is app
            mw.after_process_message(broker=None, message=None)
            assert _active_app() is outer_app
