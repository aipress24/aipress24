# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `default_new_offer_status` in
`app.modules.biz.views._offers_common`.

The policy : when the project is configured with
`MARKETPLACE_MODERATION_REQUIRED=True`, freshly-created offers go
into `PENDING` (hidden from listings, awaiting admin review). When
the flag is off (or missing), offers publish straight to `PUBLIC`.

Pin the gate so a future config-key renaming doesn't silently flip
all new offers to publish-without-review.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.models.lifecycle import PublicationStatus
from app.modules.biz.views._offers_common import default_new_offer_status

if TYPE_CHECKING:
    from flask import Flask


class TestDefaultNewOfferStatus:
    def test_returns_public_when_flag_unset(self, app: Flask):
        """No moderation flag → publish immediately. This is the
        production default for AiPress24 today."""
        with app.test_request_context():
            app.config.pop("MARKETPLACE_MODERATION_REQUIRED", None)
            assert default_new_offer_status() == PublicationStatus.PUBLIC

    def test_returns_pending_when_flag_truthy(self, app: Flask):
        """When admins enable moderation, every new offer waits for
        review. Pin the truthy-check, which is the broad « any non-
        falsy value » rather than `is True`."""
        with app.test_request_context():
            app.config["MARKETPLACE_MODERATION_REQUIRED"] = True
            assert default_new_offer_status() == PublicationStatus.PENDING

    def test_returns_pending_for_truthy_non_bool(self, app: Flask):
        """The config can carry strings or ints (env-var coercion
        from `Dynaconf`). Pin so `MARKETPLACE_MODERATION_REQUIRED="1"`
        is honoured the same way as `True`."""
        with app.test_request_context():
            app.config["MARKETPLACE_MODERATION_REQUIRED"] = "yes"
            assert default_new_offer_status() == PublicationStatus.PENDING

    def test_returns_public_when_flag_falsy(self, app: Flask):
        """Empty string / 0 / False / None all mean « no moderation »."""
        with app.test_request_context():
            for falsy in (False, 0, "", None):
                app.config["MARKETPLACE_MODERATION_REQUIRED"] = falsy
                assert default_new_offer_status() == PublicationStatus.PUBLIC, (
                    f"{falsy!r} should be treated as no-moderation"
                )

    def test_return_type_is_publication_status(self, app: Flask):
        """The caller passes the result directly to
        `MissionOffer(status=...)`. A plain string would break the
        SQLAlchemy Enum binding. Pin the type so a future
        `return "public"` regression is caught."""
        with app.test_request_context():
            result = default_new_offer_status()
        assert isinstance(result, PublicationStatus)
