# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Flask's signed-cookie sessions, which the media files leave alone."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import request
from flask.sessions import SecureCookieSessionInterface

if TYPE_CHECKING:
    from flask import Flask
    from flask.sessions import SessionMixin
    from werkzeug.wrappers import Response

# Their bytes are the same for every member, and a browser keeps them.
_UNSAVED_BLUEPRINTS = frozenset({"media"})


class SessionInterface(SecureCookieSessionInterface):
    """Does not save the session after a media file.

    Saving adds `Vary: Cookie` to a response that read the session, as the
    login check does, and can set a new cookie. A browser reuses a response
    which varies on the cookie only while every cookie of the site is the
    same: each change would send all the images again.
    """

    def save_session(
        self, app: Flask, session: SessionMixin, response: Response
    ) -> None:
        if request.blueprint in _UNSAVED_BLUEPRINTS:
            return
        super().save_session(app, session, response)
