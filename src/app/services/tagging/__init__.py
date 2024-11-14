# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from ._services import add_tag, get_tag_applications, get_tags
from .interfaces import Taggable

__all__ = ["Taggable", "add_tag", "get_tag_applications", "get_tags"]
