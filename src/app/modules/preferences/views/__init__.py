# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Preferences views using convention-driven navigation."""

from __future__ import annotations

# Import all view modules to register routes
from . import banner, contact, home, interests, invitations, others, profile

__all__ = ["banner", "contact", "home", "interests", "invitations", "others", "profile"]
