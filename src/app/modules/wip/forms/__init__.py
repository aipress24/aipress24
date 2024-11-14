# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

# flake8: noqa: F401

"""
Forms descriptions for the content objects in the WIP module.

Each form is described as a dictionary with the following keys:

- "label": ...
- "model_class": ...
- "group": { ... }
- "field": { ... }

These dictionaries are used to generate WTForms classes by the `generate-forms3.py` script.
"""

from __future__ import annotations

from .article import article_form
from .avis_enquete import avis_enquete_form
from .commande import commande_form
from .sujet import sujet_form

__all__ = ["article_form", "avis_enquete_form", "commande_form", "sujet_form"]
