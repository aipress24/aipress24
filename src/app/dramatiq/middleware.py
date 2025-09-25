"""Dramatiq middleware for Flask application context."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from threading import local

from dramatiq import Middleware


class AppContextMiddleware(Middleware):
    """Middleware to setup Flask app context for actors.

    Borrowed from https://github.com/Bogdanp/flask_dramatiq_example.
    """

    state = local()

    def __init__(self, app) -> None:
        """Initialize middleware with Flask app.

        Args:
            app: Flask application instance.
        """
        self.app = app

    def before_process_message(self, broker, message) -> None:
        """Setup Flask app context before processing message.

        Args:
            broker: Dramatiq broker instance.
            message: Message being processed.
        """
        context = self.app.app_context()
        context.push()

        self.state.context = context

    def after_process_message(
        self, broker, message, *, result=None, exception=None
    ) -> None:
        """Cleanup Flask app context after processing message.

        Args:
            broker: Dramatiq broker instance.
            message: Message that was processed.
            result: Processing result, if any.
            exception: Exception that occurred, if any.
        """
        try:
            context = self.state.context
            context.pop(exception)
            del self.state.context
        except AttributeError:
            pass

    after_skip_message = after_process_message
