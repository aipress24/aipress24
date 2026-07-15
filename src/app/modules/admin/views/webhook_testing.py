# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin view to test Stripe webhooks using real Stripe events."""

from __future__ import annotations

import time
from contextlib import suppress
from datetime import datetime
from pathlib import Path

import stripe
from flask import current_app, flash, render_template, request

from app.constants import (
    LOCAL_TZ,
    WEBHOOK_TEST_CUSTOMER_EMAIL,
    WEBHOOK_TEST_FILE_NAME,
    WEBHOOK_TEST_WAIT_TIMEOUT,
)
from app.flask.lib.nav import nav
from app.modules.admin import blueprint
from app.services.stripe.utils import load_stripe_api_key


def _now_str() -> str:
    from zoneinfo import ZoneInfo

    return datetime.now(tz=ZoneInfo(LOCAL_TZ)).strftime("%H:%M:%S")


def _webhook_flag_path() -> Path:
    """Return path of the webhook test flag file."""
    return Path(current_app.instance_path) / WEBHOOK_TEST_FILE_NAME


def _wait_for_webhook_test_flag(present: bool) -> bool:
    """Wait up to WEBHOOK_TEST_WAIT_TIMEOUT seconds for the flag file status."""
    flag_file = _webhook_flag_path()
    deadline = time.time() + WEBHOOK_TEST_WAIT_TIMEOUT
    while time.time() < deadline:
        if flag_file.exists() == present:
            return True
        time.sleep(0.1)
    return flag_file.exists() == present


@blueprint.route("/webhook_testing", methods=["GET", "POST"])
@nav(
    parent="index",
    icon="webhook",
    label="Test Webhook",
)
def webhook_testing():
    """Admin page that creates a real Stripe customer and waits for webhooks.

    Creates and delete a fake customer on Stripe, check webhooks responses.
    """
    result = None
    error = None
    messages: list[str] = []

    if request.method == "POST":
        try:
            load_stripe_api_key()

            flag_file = _webhook_flag_path()
            with suppress(OSError):
                flag_file.unlink(missing_ok=True)

            messages.append(
                f"Création du client {WEBHOOK_TEST_CUSTOMER_EMAIL} à {_now_str()}"
            )

            customer = stripe.Customer.create(
                email=WEBHOOK_TEST_CUSTOMER_EMAIL,
                name="Webhook Test Customer",
                description="Webhook Test Customer",
            )
            customer_id = customer.id

            try:
                messages.append(
                    f"Client Stripe créé ({customer_id}), attente du webhook "
                    "customer.created..."
                )
                if not _wait_for_webhook_test_flag(present=True):
                    created_timeout_msg = (
                        "Le webhook customer.created n'a pas été reçu"
                        f"(timeout {WEBHOOK_TEST_WAIT_TIMEOUT}s)."
                    )
                    raise RuntimeError(created_timeout_msg)
                messages.append(f'Webhook "customer.created" reçu à {_now_str()}')

                messages.append(
                    f"Demande de suppression du client Stripe à {_now_str()}"
                )
                stripe.Customer.delete(customer_id)

                messages.append("Attente du webhook customer.deleted...")
                if not _wait_for_webhook_test_flag(present=False):
                    deleted_timeout_msg = (
                        "Le webhook customer.deleted n'a pas été reçu "
                        f"(timeout {WEBHOOK_TEST_WAIT_TIMEOUT}s)."
                    )
                    raise RuntimeError(deleted_timeout_msg)
                messages.append(f"Webhook customer.deleted reçu à {_now_str()}")

                result = "Test webhook Stripe OK."
                flash(result, "success")
            finally:
                with suppress(OSError):
                    flag_file.unlink(missing_ok=True)

        except Exception as e:
            error = f"Échec du test webhook : {e}"
            flash(error, "error")

    return render_template(
        "admin/pages/webhook_testing.j2",
        title="Test Webhook",
        result=result,
        error=error,
        messages=messages,
    )
