# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Event views using convention-driven navigation.

This package replaces the Page-based views in pages/ with plain Flask views.
Each module corresponds to one page/view.
"""

from __future__ import annotations

# Import all view modules to register routes on the blueprint
from . import calendar, event_detail, events_list

__all__ = ["calendar", "event_detail", "events_list"]
