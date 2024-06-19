# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""### Des compteurs pour le calcul de la réputation

1- On sort la réputation de WIP.
2- La réputation va dans profil
3- On rebaptise "Performances"

A faire: les Devs et les étudiants
"""

from __future__ import annotations

from ._compute import compute_reputation

__all__ = ["compute_reputation"]
