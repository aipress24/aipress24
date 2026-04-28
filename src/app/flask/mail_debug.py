# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""In-memory mail backend + ``/debug/mail`` blueprint for e2e tests.

Drops a flask-mailman backend that captures messages into a
process-local list instead of opening an SMTP connection, plus a
small read-only HTTP surface for tests to inspect the inbox and
reset it between runs. Same fail-closed pattern as flask-coverage :
registration is refused unless the app is in debug mode or the
``FLASK_MAIL_DEBUG_PASSWORD`` env var is set.

Tests typically use the ``mail_outbox`` fixture in the e2e suite ;
this module is the server side.
"""

from __future__ import annotations

import hmac
import os
from datetime import UTC, datetime
from threading import Lock
from typing import TYPE_CHECKING

from flask import (
    Blueprint,
    Response,
    current_app,
    jsonify,
    redirect,
    render_template_string,
    request,
)
from flask_mailman.backends.base import BaseEmailBackend

if TYPE_CHECKING:
    from flask import Flask
    from flask_mailman.message import EmailMessage

# Process-local message store. Each entry is a dict — already-
# serialised, so /debug/mail/messages is a simple jsonify().
_inbox: list[dict] = []
_lock = Lock()


def reset() -> None:
    """Clear the captured-message buffer."""
    with _lock:
        _inbox.clear()


def messages() -> list[dict]:
    """Return a snapshot copy of all captured messages."""
    with _lock:
        return list(_inbox)


def is_active() -> bool:
    """True when the memory backend is wired up. Used by
    `email_limiter` helpers to short-circuit the quota check."""
    try:
        return bool(current_app.config.get("MAIL_DEBUG_ACTIVE"))
    except RuntimeError:
        return False


class EmailBackend(BaseEmailBackend):
    """flask-mailman backend that stores each message in `_inbox`
    instead of sending it. Returns the count of accepted messages
    so the caller's success heuristic still passes."""

    def send_messages(self, email_messages: list[EmailMessage]) -> int:
        if not email_messages:
            return 0
        sent = 0
        for msg in email_messages:
            try:
                with _lock:
                    _inbox.append(_serialise(msg))
                sent += 1
            except Exception:
                if not self.fail_silently:
                    raise
        return sent


def _serialise(msg: EmailMessage) -> dict:
    return {
        "subject": msg.subject,
        "from": msg.from_email,
        "to": list(msg.to or []),
        "cc": list(msg.cc or []),
        "bcc": list(msg.bcc or []),
        "reply_to": list(msg.reply_to or []),
        "body": msg.body,
        "content_subtype": msg.content_subtype,
        "headers": dict(msg.extra_headers or {}),
        "captured_at": datetime.now(UTC).isoformat(),
    }


# ----- HTTP surface ------------------------------------------------

_DASHBOARD = """\
<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Mail debug</title>
<style>
body { font-family: system-ui, sans-serif; max-width: 1100px;
       margin: 1.5em auto; padding: 0 1em; }
h1 { margin-bottom: 0.2em; }
.count { color: #555; font-size: 0.95em; }
table { border-collapse: collapse; width: 100%; margin-top: 1em; }
th, td { padding: 0.5em 0.75em; border-bottom: 1px solid #ddd;
         text-align: left; vertical-align: top; }
th { background: #f4f4f4; }
tr:hover { background: #fafafa; }
form { display: inline; }
button { padding: 0.4em 0.9em; }
.subj { font-weight: 500; max-width: 480px; }
small { color: #888; }
</style></head><body>
<h1>Mail debug</h1>
<p class="count">{{ messages|length }} message(s) captured.</p>
<form method="post" action="/debug/mail/reset">
  <button type="submit">Reset</button>
</form>
<table>
  <thead><tr><th>#</th><th>Captured</th><th>From → To</th>
  <th class="subj">Subject</th></tr></thead>
  <tbody>
  {% for m in messages %}
    <tr>
      <td><a href="/debug/mail/messages/{{ loop.index0 }}">{{ loop.index0 }}</a></td>
      <td><small>{{ m["captured_at"] }}</small></td>
      <td>{{ m["from"] }}<br><small>→ {{ m["to"]|join(", ") }}</small></td>
      <td class="subj">{{ m["subject"] }}</td>
    </tr>
  {% endfor %}
  </tbody>
</table>
</body></html>
"""


def make_blueprint() -> Blueprint:
    bp = Blueprint("mail_debug", __name__)

    @bp.before_request
    def _gate() -> Response | None:
        # `app.debug` is checked at registration time but recheck
        # here for password-only deployments.
        password = os.environ.get("FLASK_MAIL_DEBUG_PASSWORD")
        if not password and not current_app.debug:
            return Response("forbidden", status=403)
        if password:
            auth = request.authorization
            user = os.environ.get("FLASK_MAIL_DEBUG_USERNAME", "admin")
            if not auth or not (
                hmac.compare_digest(auth.username or "", user)
                and hmac.compare_digest(auth.password or "", password)
            ):
                return Response(
                    "auth required",
                    status=401,
                    headers={"WWW-Authenticate": 'Basic realm="mail-debug"'},
                )
        return None

    @bp.route("/")
    def dashboard() -> str:
        return render_template_string(_DASHBOARD, messages=messages())

    @bp.route("/messages")
    def list_messages() -> Response:
        return jsonify(messages())

    @bp.route("/messages/<int:idx>")
    def get_message(idx: int) -> Response:
        snap = messages()
        if not 0 <= idx < len(snap):
            return Response("not found", status=404)
        return jsonify(snap[idx])

    @bp.route("/reset", methods=["POST"])
    def reset_buffer():
        reset()
        if request.headers.get("Accept") == "application/json":
            return jsonify({"status": "reset", "count": 0})
        return redirect("/debug/mail/")

    return bp


class MailDebug:
    """Flask extension : forces ``MAIL_BACKEND`` to the memory
    backend defined here and mounts the dashboard.

    Fail-closed : raises ``RuntimeError`` unless ``app.debug`` is
    True or ``FLASK_MAIL_DEBUG_PASSWORD`` is set in the env."""

    def __init__(self, app: Flask | None = None) -> None:
        if app is not None:
            self.init_app(app)

    def init_app(self, app: Flask) -> None:
        password = os.environ.get("FLASK_MAIL_DEBUG_PASSWORD")
        if not (app.debug or password):
            msg = (
                "MailDebug refusing to register: app is not in debug "
                "mode and FLASK_MAIL_DEBUG_PASSWORD is not set."
            )
            raise RuntimeError(msg)
        backend_path = "app.flask.mail_debug.EmailBackend"
        app.config["MAIL_BACKEND"] = backend_path
        app.config["MAIL_DEBUG_ACTIVE"] = True
        # Override the already-initialized flask-mailman backend.
        # `init_app` caches `mailman.backend` from MAIL_BACKEND ;
        # mutating the config alone would not propagate.
        mailman = app.extensions.get("mailman")
        if mailman is not None:
            mailman.backend = backend_path
        app.register_blueprint(make_blueprint(), url_prefix="/debug/mail")
