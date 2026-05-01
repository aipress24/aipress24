# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""In-tree Stripe mock + ``/debug/stripe`` blueprint for e2e tests.

Same fail-closed pattern as ``flask-mail-debug`` and
``flask-coverage`` : registration is refused unless the app is in
debug mode or ``FLASK_STRIPE_DEBUG_PASSWORD`` is set in env.

When active :

- Monkey-patches ``stripe.checkout.Session.create`` to return a
  synthetic ``MockSession`` whose ``.url`` is the call's
  ``success_url`` — the user's redirect short-circuits the real
  Stripe checkout page and lands directly on the app's success
  handler. No network calls to Stripe.
- Captures every call's args + the synthetic session into a
  process-local list, exposed via ``/debug/stripe/sessions``.
- Force-enables ``STRIPE_LIVE_ENABLED`` for the duration so the
  app code doesn't short-circuit the buy/subscribe path before
  the mock kicks in.

Webhook simulation (POST a synthetic ``checkout.session.completed``
event back to ``/webhook``) is **not** included in this phase —
Phase 2. Most e2e flows can be tested with the simple session-
redirect mock alone, since the user-visible state changes happen
on the success_url path.
"""

from __future__ import annotations

import hmac
import os
import time
from threading import Lock
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from flask import (
    Blueprint,
    Response,
    current_app,
    jsonify,
    redirect,
    render_template_string,
    request,
)

if TYPE_CHECKING:
    from flask import Flask


_DEFAULT_BUCKET = "default"
_sessions: dict[str, list[dict]] = {_DEFAULT_BUCKET: []}
_lock = Lock()


def _bucket_for(worker: str | None) -> str:
    return worker or _DEFAULT_BUCKET


def _request_worker() -> str:
    """Same-shape helper as mail_debug — namespacing by
    ``X-Mail-Worker`` header so xdist-parallel runs don't
    cross-pollute. Re-uses the same header (one knob)."""
    try:
        return request.headers.get("X-Mail-Worker", "") or _DEFAULT_BUCKET
    except RuntimeError:
        return _DEFAULT_BUCKET


def reset(worker: str | None = None) -> None:
    bucket = _bucket_for(worker)
    with _lock:
        _sessions[bucket] = []


def sessions(worker: str | None = None) -> list[dict]:
    bucket = _bucket_for(worker)
    with _lock:
        return list(_sessions.get(bucket, []))


class MockSession:
    """Minimal stand-in for ``stripe.checkout.Session``. Carries
    the ``url`` that the app's ``redirect(checkout.url)`` will
    follow ; everything else is best-effort."""

    def __init__(self, **kwargs: Any) -> None:
        self.id = f"cs_test_{uuid4().hex[:24]}"
        self.url = kwargs.get("success_url") or "/debug/stripe/auto-success"
        self.payment_status = "paid"
        self.status = "complete"
        self.mode = kwargs.get("mode", "payment")
        self.customer_email = kwargs.get("customer_email")
        self.metadata = kwargs.get("metadata", {})
        self.line_items = kwargs.get("line_items", [])
        self._raw = kwargs

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "url": self.url,
            "mode": self.mode,
            "status": self.status,
            "payment_status": self.payment_status,
            "customer_email": self.customer_email,
            "metadata": dict(self.metadata or {}),
            "captured_at": time.time(),
        }


def _patched_session_create(*args: Any, **kwargs: Any) -> MockSession:
    """Replacement for ``stripe.checkout.Session.create`` when the
    mock is active. Returns a ``MockSession`` whose ``.url`` is the
    caller-provided ``success_url`` — when the app redirects to it,
    the user immediately lands on the success handler."""
    session = MockSession(**kwargs)
    bucket = _bucket_for(_request_worker())
    with _lock:
        _sessions.setdefault(bucket, []).append(session.to_dict())
    return session


def is_active() -> bool:
    """True when the mock is wired up. Used by tests / debug."""
    try:
        return bool(current_app.config.get("STRIPE_DEBUG_ACTIVE"))
    except RuntimeError:
        return False


# ─── HTTP surface ──────────────────────────────────────────────────


_DASHBOARD = """\
<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Stripe debug</title>
<style>
body { font-family: system-ui, sans-serif; max-width: 1100px;
       margin: 1.5em auto; padding: 0 1em; }
h1 { margin-bottom: 0.2em; }
.count { color: #555; font-size: 0.95em; }
table { border-collapse: collapse; width: 100%; margin-top: 1em; }
th, td { padding: 0.5em 0.75em; border-bottom: 1px solid #ddd;
         text-align: left; vertical-align: top; }
th { background: #f4f4f4; }
form { display: inline; }
button { padding: 0.4em 0.9em; }
small { color: #888; }
code { font-family: ui-monospace, Menlo, monospace; font-size: 0.9em; }
</style></head><body>
<h1>Stripe debug</h1>
<p class="count">{{ sessions|length }} checkout session(s) captured.</p>
<form method="post" action="/debug/stripe/reset">
  <button type="submit">Reset</button>
</form>
<table>
  <thead><tr><th>#</th><th>Captured</th><th>Mode</th>
  <th>Customer</th><th>Metadata</th><th>URL</th></tr></thead>
  <tbody>
  {% for s in sessions %}
    <tr>
      <td>{{ loop.index0 }}</td>
      <td><small>{{ s["captured_at"] }}</small></td>
      <td><code>{{ s["mode"] }}</code></td>
      <td>{{ s["customer_email"] }}</td>
      <td><code>{{ s["metadata"] }}</code></td>
      <td><code>{{ s["url"] }}</code></td>
    </tr>
  {% endfor %}
  </tbody>
</table>
</body></html>
"""


def make_blueprint() -> Blueprint:
    bp = Blueprint("stripe_debug", __name__)

    @bp.before_request
    def _gate() -> Response | None:
        password = os.environ.get("FLASK_STRIPE_DEBUG_PASSWORD")
        if not password and not current_app.debug:
            return Response("forbidden", status=403)
        if password:
            auth = request.authorization
            user = os.environ.get("FLASK_STRIPE_DEBUG_USERNAME", "admin")
            if not auth or not (
                hmac.compare_digest(auth.username or "", user)
                and hmac.compare_digest(auth.password or "", password)
            ):
                return Response(
                    "auth required",
                    status=401,
                    headers={"WWW-Authenticate": 'Basic realm="stripe-debug"'},
                )
        return None

    @bp.route("/")
    def dashboard() -> str:
        return render_template_string(_DASHBOARD, sessions=sessions())

    @bp.route("/sessions")
    def list_sessions() -> Response:
        return jsonify(sessions(_request_worker()))

    @bp.route("/reset", methods=["POST"])
    def reset_buffer():
        reset(_request_worker())
        if request.headers.get("Accept") == "application/json":
            return jsonify({"status": "reset", "count": 0})
        return redirect("/debug/stripe/")

    @bp.route("/auto-success")
    def auto_success() -> str:
        """Fallback landing page — used when a Stripe call provides
        no `success_url`. Tests should generally use the app's own
        success route."""
        return (
            "<html><body><h1>Stripe checkout completed (mock)</h1>"
            "<p>This is the in-tree Stripe debug auto-success "
            "page.</p></body></html>"
        )

    return bp


# ─── Extension ─────────────────────────────────────────────────────


class StripeDebug:
    """Flask extension : monkey-patches ``stripe.checkout.Session.create``
    to short-circuit the real Stripe API and route the user
    directly to the caller's ``success_url``.

    Fail-closed : raises ``RuntimeError`` unless ``app.debug`` is
    True or ``FLASK_STRIPE_DEBUG_PASSWORD`` is set in the env."""

    def __init__(self, app: Flask | None = None) -> None:
        if app is not None:
            self.init_app(app)

    def init_app(self, app: Flask) -> None:
        password = os.environ.get("FLASK_STRIPE_DEBUG_PASSWORD")
        if not (app.debug or password):
            msg = (
                "StripeDebug refusing to register: app is not in "
                "debug mode and FLASK_STRIPE_DEBUG_PASSWORD is not "
                "set."
            )
            raise RuntimeError(msg)

        # Force-enable the buy/subscribe paths — without this, the
        # app code short-circuits with a flash "online purchases
        # not yet activated" before reaching the Stripe SDK call.
        app.config["STRIPE_LIVE_ENABLED"] = True
        app.config["STRIPE_DEBUG_ACTIVE"] = True
        # Provide a placeholder API key so `load_stripe_api_key`
        # doesn't bail. The real Stripe SDK won't be called.
        app.config.setdefault("STRIPE_SECRET_KEY", "sk_test_mock_inline")
        # Placeholder Stripe price IDs for the one-off wire products
        # (cf. wire/views/purchase.py:_PRODUCT_TO_ENV) and for the
        # BW pricing tables. The mock doesn't validate — these just
        # let the routes pass the `if not price_id: bail` guard.
        for env in (
            "STRIPE_PRICE_CONSULTATION",
            "STRIPE_PRICE_JUSTIFICATIF",
            "STRIPE_PRICE_CESSION",
            "STRIPE_PRICING_SUBS_MEDIA",
            "STRIPE_PRICING_SUBS_MICRO",
            "STRIPE_PRICING_SUBS_PR",
            "STRIPE_PRICING_SUBS_LEADERS_EXPERTS",
            "STRIPE_PRICING_SUBS_TRANSFORMERS",
            "STRIPE_PRICING_SUBS_CORPORATE_MEDIA",
            "STRIPE_PRICING_SUBS_ACADEMICS",
            "STRIPE_PRICING_SUBS_UNION",
        ):
            app.config.setdefault(env, f"price_mock_{env.lower()}")

        # Monkey-patch the Stripe SDK. Idempotent : a second
        # init_app on the same process is a no-op.
        import stripe

        if getattr(stripe.checkout.Session, "_stripe_debug_patched", False):
            pass
        else:
            stripe.checkout.Session.create = staticmethod(  # type: ignore[method-assign]
                _patched_session_create
            )
            stripe.checkout.Session._stripe_debug_patched = True  # type: ignore[attr-defined]

        app.register_blueprint(make_blueprint(), url_prefix="/debug/stripe")
