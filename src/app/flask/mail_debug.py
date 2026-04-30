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

# Process-local message store, namespaced by worker_id so pytest-xdist
# parallel runs don't cross-pollute. Default bucket is `"default"`
# for sequential runs (no `X-Mail-Worker` header sent).
_DEFAULT_BUCKET = "default"
_inbox: dict[str, list[dict]] = {_DEFAULT_BUCKET: []}
_lock = Lock()


def _bucket_for(worker: str | None) -> str:
    """Resolve a worker tag to a bucket key. Empty / None → default."""
    return worker or _DEFAULT_BUCKET


def reset(worker: str | None = None) -> None:
    """Clear the captured-message buffer for ``worker`` (or default)."""
    bucket = _bucket_for(worker)
    with _lock:
        _inbox[bucket] = []


def messages(worker: str | None = None) -> list[dict]:
    """Return a snapshot copy of all messages captured for ``worker``."""
    bucket = _bucket_for(worker)
    with _lock:
        return list(_inbox.get(bucket, []))


def _request_worker() -> str:
    """Extract the `X-Mail-Worker` header from the current request,
    if any. Used by both the EmailBackend (when a server-side mail
    send is triggered by an authenticated test request) and by the
    debug HTTP routes (when the test fetches the buffer directly,
    routing on the same header)."""
    try:
        return request.headers.get("X-Mail-Worker", "") or _DEFAULT_BUCKET
    except RuntimeError:
        # Outside a request context (e.g. CLI commands sending mail).
        return _DEFAULT_BUCKET


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
        # Resolve the worker bucket from the originating request's
        # `X-Mail-Worker` header. Mail sends triggered outside a
        # request context (CLI commands, scheduler) fall into the
        # default bucket.
        bucket = _bucket_for(_request_worker())
        sent = 0
        for msg in email_messages:
            try:
                with _lock:
                    _inbox.setdefault(bucket, []).append(_serialise(msg))
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
        # Dashboard always renders the default bucket (humans browsing
        # the dev server). Test fixtures use the JSON endpoints with
        # the X-Mail-Worker header.
        return render_template_string(_DASHBOARD, messages=messages())

    @bp.route("/messages")
    def list_messages() -> Response:
        return jsonify(messages(_request_worker()))

    @bp.route("/messages/<int:idx>")
    def get_message(idx: int) -> Response:
        snap = messages(_request_worker())
        if not 0 <= idx < len(snap):
            return Response("not found", status=404)
        return jsonify(snap[idx])

    @bp.route("/reset", methods=["POST"])
    def reset_buffer():
        reset(_request_worker())
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
