# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

# flake8: noqa: F401

from __future__ import annotations

from .article import article_form
from .avis_enquete import avis_enquete_form
from .commande import commande_form
from .sujet import sujet_form

__all__ = ["article_form", "avis_enquete_form", "commande_form", "sujet_form"]
