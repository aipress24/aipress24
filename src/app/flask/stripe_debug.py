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
- Force-enables ``STRIPE_LIVE_ENABLED`` and provides placeholder
  STRIPE_PRICE_* / STRIPE_PRICING_SUBS_* config keys.
- Monkey-patches ``stripe.Webhook.construct_event`` to skip
  signature verification when called via the in-tree mock —
  tests can POST raw JSON event payloads to ``/webhook``
  without forging an HMAC.
- ``/debug/stripe/fire-webhook`` POST helper : tests pass a
  ``session_id`` (or arbitrary event payload) ; the route
  builds a synthetic event and POSTs it to ``/webhook``
  internally via the test client. Drives the full webhook
  handler chain (`on_checkout_session_completed`,
  `_record_article_purchase_from_checkout`,
  `_activate_bw_from_checkout`, etc.) end-to-end.
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


def _patched_session_create(*_args: Any, **kwargs: Any) -> MockSession:
    """Replacement for ``stripe.checkout.Session.create`` when the
    mock is active. Returns a ``MockSession`` whose ``.url`` is the
    caller-provided ``success_url`` — when the app redirects to it,
    the user immediately lands on the success handler.

    Positional args are accepted to match Stripe's API (the SDK
    accepts both styles) but only kwargs are read."""
    session = MockSession(**kwargs)
    bucket = _bucket_for(_request_worker())
    with _lock:
        _sessions.setdefault(bucket, []).append(session.to_dict())
    return session


def _patched_construct_event(
    payload: bytes | str,
    _sig_header: str | None,
    _secret: str,
    *_args: Any,
    **_kwargs: Any,
) -> Any:
    """Replacement for ``stripe.Webhook.construct_event`` when the
    mock is active : skip the HMAC signature verification entirely
    and just return the parsed event. Tests can POST a raw JSON
    payload to ``/webhook`` with any (or no) ``Stripe-Signature``
    header — the webhook handler accepts it and runs the full
    event-dispatch chain.

    The signature / secret arguments are kept on the function
    signature (prefixed with `_`) only to match Stripe's
    ``construct_event`` API — the mock intentionally ignores them.

    Safe : guarded by ``STRIPE_DEBUG_ACTIVE`` config flag (set only
    when the mock extension is registered, which itself is
    fail-closed on debug mode).
    """
    import json

    from stripe import Event

    if isinstance(payload, bytes):
        payload = payload.decode("utf-8")
    data = json.loads(payload)
    return Event.construct_from(data, "sk_test_mock_inline")


# ─── Synthetic resource retrievers ─────────────────────────────────


def _patched_customer_retrieve(item_id: str, **kwargs: Any) -> Any:
    """Synthetic ``stripe.Customer.retrieve`` — returns a Customer-
    shaped dict. The webhook handler accesses ``customer["email"]``
    only, so a minimal payload suffices."""
    from stripe import Customer

    return Customer.construct_from(
        {
            "id": item_id,
            "object": "customer",
            "email": f"{item_id}@mock-stripe.invalid",
            "name": "Mock Customer",
        },
        "sk_test_mock_inline",
    )


def _patched_product_retrieve(item_id: str, **kwargs: Any) -> Any:
    """Synthetic ``stripe.Product.retrieve`` — returns a Product
    with ``metadata.BW`` set to a placeholder so the webhook's
    ``_check_subscription_product`` falls into the « OTHER » branch
    (returns True). Tests fire customer.subscription.* events
    against arbitrary user emails without provisioning a matching
    BW row, so OTHER is the safe path."""
    from stripe import Product

    return Product.construct_from(
        {
            "id": item_id,
            "object": "product",
            "name": f"Mock Product {item_id}",
            "metadata": {"BW": "other"},
        },
        "sk_test_mock_inline",
    )


def _patched_invoice_retrieve(item_id: str, **kwargs: Any) -> Any:
    """Synthetic ``stripe.Invoice.retrieve`` — minimal payload with
    a hosted invoice URL placeholder."""
    from stripe import Invoice

    return Invoice.construct_from(
        {
            "id": item_id,
            "object": "invoice",
            "hosted_invoice_url": f"https://mock-stripe.invalid/invoice/{item_id}",
        },
        "sk_test_mock_inline",
    )


def _patched_billing_portal_session_create(*_args: Any, **kwargs: Any) -> Any:
    """Synthetic ``stripe.billing_portal.Session.create`` — used by
    `bw/bw_activation/routes/billing_portal.py:billing_portal`.
    The route follows ``portal_session.url`` via 303 redirect, so
    we just need a URL the browser can land on. Point it at the
    debug auto-success page."""
    return _MockBillingPortalSession(
        return_url=kwargs.get("return_url", ""),
    )


class _MockBillingPortalSession:
    def __init__(self, *, return_url: str) -> None:
        self.id = f"bps_test_{uuid4().hex[:24]}"
        self.url = return_url or "/debug/stripe/auto-success"


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

    @bp.route("/fire-webhook", methods=["POST"])
    def fire_webhook() -> Response | tuple[Response, int]:
        """Build a synthetic Stripe webhook event and POST it
        internally to ``/webhook``. Tests use this to drive the
        webhook handler after a checkout flow (since real Stripe
        wouldn't deliver in dev).

        Two modes :
        - **From captured session** : pass ``session_id`` (or omit
          to use the latest captured). Used by the wire purchase
          path where Stripe call is server-side and intercepted.
        - **Synthetic** : pass ``synthetic=1`` + form params
          (``bw_id``, ``mode``, ``customer_email``). Used for
          client-side checkout flows (BW paid activation via
          Stripe Pricing Table widget) where no captured session
          exists.

        Other form params :
        - ``event_type`` : default
          ``"checkout.session.completed"`` ; can be set to any
          handled type from `_EVENT_HANDLER_NAMES` in
          ``stripe.views.webhook``.
        """
        from uuid import uuid4

        worker = _request_worker()
        captured = sessions(worker)
        session_id = request.form.get("session_id", "")
        event_type = request.form.get("event_type", "checkout.session.completed")
        synthetic = request.form.get("synthetic") == "1"

        # Resolve the source session.
        src: dict | None = None
        if synthetic:
            mode = request.form.get("mode", "subscription")
            bw_id = request.form.get("bw_id", "")
            customer_email = request.form.get("customer_email", "")
            metadata: dict = {}
            if bw_id:
                metadata["bw_id"] = bw_id
            src = {
                "id": f"cs_test_synthetic_{uuid4().hex[:16]}",
                "mode": mode,
                "status": "complete",
                "payment_status": "paid",
                "customer_email": customer_email,
                "metadata": metadata,
            }
        else:
            if session_id:
                src = next(
                    (s for s in captured if s.get("id") == session_id),
                    None,
                )
            elif captured:
                src = captured[-1]
            if src is None:
                return jsonify(
                    {
                        "error": "no captured session matches session_id",
                        "session_id": session_id,
                        "captured_count": len(captured),
                    }
                ), 404

        # Build a minimal-but-realistic event payload. The webhook
        # handler accesses event.type, event.id, event.data.object
        # and within the object various per-event-type fields.
        event_id = f"evt_test_{uuid4().hex[:24]}"
        raw_metadata = src.get("metadata") or {}

        if event_type.startswith("customer.subscription."):
            # data.object is a Subscription — populate every field
            # accessed by `_make_customer_subscription_info` and
            # `_check_subscription_product`. Customer/Product/
            # Invoice retrievals are mocked at extension load time.
            now_ts = int(time.time())
            sub_id = f"sub_test_{uuid4().hex[:16]}"
            customer_id = (
                request.form.get("customer_id") or f"cus_test_{uuid4().hex[:16]}"
            )
            data_obj = {
                "id": sub_id,
                "object": "subscription",
                "customer": customer_id,
                "created": now_ts - 60,
                "current_period_start": now_ts,
                "current_period_end": now_ts + 30 * 86400,
                "quantity": int(request.form.get("quantity", "1")),
                "status": request.form.get("sub_status", "active"),
                "plan": {
                    "id": f"price_mock_{uuid4().hex[:8]}",
                    "nickname": "BW4PR_Y",
                    "interval": "month",
                    "product": f"prod_mock_{uuid4().hex[:8]}",
                },
                "latest_invoice": (f"in_test_{uuid4().hex[:16]}"),
            }
        else:
            # Default (checkout.session.* + subscription_schedule.*
            # + unmanaged) : checkout.session-shaped object.
            data_obj = {
                "id": src["id"],
                "object": "checkout.session",
                "mode": src.get("mode", "payment"),
                "status": src.get("status", "complete"),
                "payment_status": src.get("payment_status", "paid"),
                "customer_email": src.get("customer_email"),
                "metadata": raw_metadata,
                "client_reference_id": raw_metadata.get("bw_id"),
                "amount_total": 1000,
                "currency": "eur",
                "payment_intent": f"pi_test_{uuid4().hex[:24]}",
                # In synthetic mode (BW paid activation tests),
                # leave `customer` empty so the cancel-
                # subscription cleanup path doesn't bail with
                # "go to Stripe portal" (which it does when
                # subscription.stripe_customer_id is truthy
                # AND STRIPE_LIVE_ENABLED is True).
                "customer": ("" if synthetic else f"cus_test_{uuid4().hex[:24]}"),
                "subscription": (
                    f"sub_test_{uuid4().hex[:24]}"
                    if src.get("mode") == "subscription"
                    else None
                ),
            }
        event_payload = {
            "id": event_id,
            "object": "event",
            "type": event_type,
            "data": {"object": data_obj},
        }

        # POST internally to /webhook via the test client.
        # This stays in-process so the webhook's DB writes share
        # the same dev-server context.
        with current_app.test_client() as client:
            resp = client.post(
                "/webhook",
                json=event_payload,
                headers={
                    "Stripe-Signature": "t=0,v1=mock",
                    "Content-Type": "application/json",
                    "X-Mail-Worker": worker,
                },
            )
            return jsonify(
                {
                    "fired": True,
                    "event_id": event_id,
                    "event_type": event_type,
                    "session_id": src["id"],
                    "webhook_status": resp.status_code,
                    "webhook_body": resp.get_data(as_text=True)[:500],
                }
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

        # Set a placeholder STRIPE_WEBHOOK_SECRET so the webhook
        # handler doesn't `raise ValueError` on the missing-secret
        # check before we get to the construct_event monkey-patch.
        app.config.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_mock_inline")

        # Monkey-patch the Stripe SDK. Idempotent : a second
        # init_app on the same process is a no-op.
        import stripe

        if not getattr(stripe.checkout.Session, "_stripe_debug_patched", False):
            stripe.checkout.Session.create = staticmethod(  # type: ignore[method-assign]
                _patched_session_create
            )
            stripe.checkout.Session._stripe_debug_patched = True  # type: ignore[attr-defined]

        if not getattr(stripe.Webhook, "_stripe_debug_patched", False):
            stripe.Webhook.construct_event = staticmethod(  # type: ignore[method-assign]
                _patched_construct_event
            )
            stripe.Webhook._stripe_debug_patched = True  # type: ignore[attr-defined]

        # Patch Customer/Product/Invoice retrieve to return synthetic
        # objects. Used by `customer.subscription.*` event handlers
        # which call `retrieve_customer`, `retrieve_product`,
        # `retrieve_invoice` from `services/stripe/retriever.py`.
        for klass, fn in (
            (stripe.Customer, _patched_customer_retrieve),
            (stripe.Product, _patched_product_retrieve),
            (stripe.Invoice, _patched_invoice_retrieve),
        ):
            if not getattr(klass, "_stripe_debug_patched", False):
                klass.retrieve = staticmethod(fn)  # type: ignore[method-assign]
                klass._stripe_debug_patched = True  # type: ignore[attr-defined]

        # Patch the Billing Portal Session.create — used by
        # `bw/bw_activation/routes/billing_portal.py` to redirect
        # users to Stripe's hosted customer portal. The route
        # follows the returned `.url` via 303, so a synthetic
        # session pointing at our debug auto-success page is
        # enough for the redirect to resolve cleanly.
        if not getattr(
            stripe.billing_portal.Session,
            "_stripe_debug_patched",
            False,
        ):
            stripe.billing_portal.Session.create = staticmethod(  # type: ignore[method-assign]
                _patched_billing_portal_session_create
            )
            stripe.billing_portal.Session._stripe_debug_patched = True  # type: ignore[attr-defined]

        # Patch the Dramatiq `generate_justificatif` actor so its
        # `.send()` runs the underlying PDF-generation function
        # inline rather than enqueueing to Redis (not available in
        # dev). Same idempotency guard pattern. The patch is
        # narrowly targeted at this actor — other Dramatiq actors
        # are unaffected.
        try:
            from app.actors.justificatif import generate_justificatif

            if not getattr(generate_justificatif, "_stripe_debug_patched", False):
                generate_justificatif.send = generate_justificatif.fn  # type: ignore[method-assign]
                generate_justificatif._stripe_debug_patched = True  # type: ignore[attr-defined]
        except ImportError:
            pass

        app.register_blueprint(make_blueprint(), url_prefix="/debug/stripe")
