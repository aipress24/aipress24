# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Erreurs du domaine."""

from __future__ import annotations


class BusinessRuleError(ValueError):
    """Une règle métier refuse l'opération, et le message est pour
    l'utilisateur.

    Hérite de `ValueError` **exprès** : les routes qui attrapent déjà
    `ValueError` autour d'une transition de modèle continuent de
    fonctionner sans changement, et le passage à cette classe est un
    resserrement, pas une rupture.

    Ce qu'elle apporte est la distinction que `ValueError` ne fait pas :
    « ce que vous demandez est interdit, voici pourquoi » n'est pas
    « le programme a reçu une valeur qu'il n'attendait pas ». Le socle
    de l'atelier montre le premier à l'auteur ; le second doit remonter.
    """
