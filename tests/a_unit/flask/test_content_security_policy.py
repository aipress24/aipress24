# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""The production content security policy lets the forms reach their target."""

from __future__ import annotations

from pathlib import Path

import pytest
from dynaconf import Dynaconf

SETTINGS = Path(__file__).resolve().parents[3] / "etc" / "settings.toml"


# A form posts to the app, which redirects to these hosts. Browsers apply
# `form-action` to that redirect, and block it without a word (bug #0411).
@pytest.mark.parametrize(
    "host",
    [
        "https://checkout.stripe.com",  # Stripe Checkout
        "https://billing.stripe.com",  # Stripe customer portal
    ],
)
def test_the_forms_may_redirect_to_stripe(host: str):
    settings = Dynaconf(settings_files=[SETTINGS], environments=True, env="production")

    assert host in settings.CONTENT_SECURITY_POLICY["form-action"]
