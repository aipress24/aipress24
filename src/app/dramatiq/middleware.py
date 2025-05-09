# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from threading import local

from dramatiq import Middleware


class AppContextMiddleware(Middleware):
    # Setup Flask app for actor. Borrowed from
    # https://github.com/Bogdanp/flask_dramatiq_example.

    state = local()

    def __init__(self, app) -> None:
        self.app = app

    def before_process_message(self, broker, message) -> None:
        context = self.app.app_context()
        context.push()

        self.state.context = context

    def after_process_message(
        self, broker, message, *, result=None, exception=None
    ) -> None:
        try:
            context = self.state.context
            context.pop(exception)
            del self.state.context
        except AttributeError:
            pass

    after_skip_message = after_process_message
