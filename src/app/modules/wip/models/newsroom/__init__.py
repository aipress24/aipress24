# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""
Specs:

- Sujets
- Commande
- Avis d'enquête
- Articles
- Justificatif de publication
- Recette (?)
"""

from __future__ import annotations

# flake8: noqa: F401
from .article import Article
from .avis_enquete import AvisEnquete, ContactAvisEnquete
from .commande import Commande
from .justif_publication import JustifPublication
from .sujet import Sujet

__all__ = [
    "Article",
    "AvisEnquete",
    "Commande",
    "ContactAvisEnquete",
    "JustifPublication",
    "Sujet",
]
