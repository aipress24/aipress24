# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""Repositories for the events module.

Events are ``Publishable`` content, so visibility (published, not expired)
comes from the shared ``PublishableRepository``. The expiry column is
``expired_at`` (the ``Publishable`` convention), not wire's ``expires_at``.
"""

from __future__ import annotations

from flask_super.decorators import service

from app.services.repositories import PublishableRepository

from .models import EventPost


@service
class EventPostRepository(PublishableRepository[EventPost]):
    """Repository for EventPost, with visibility-gated reads."""

    model_type = EventPost
    expiry_attr = "expired_at"
