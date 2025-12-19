# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from itertools import pairwise

from flask import g

from app.services.reputation import get_reputation_history

from .base import BaseWipPage
from .home import HomePage

__all__ = ["PerformancePage"]


# Disabled: migrated to views/performance.py
# @page
class PerformancePage(BaseWipPage):
    name = "performance"
    label = "Performance"
    title = "Suivre ma performance réputationnelle"
    icon = "star"

    parent = HomePage

    def context(self):
        user = g.user
        assert user

        reputation_history = get_reputation_history(user)

        assert is_sorted(reputation_history, key=lambda x: x.date)

        labels = []
        data = []
        for record in reputation_history:
            labels.append(record.date.strftime("%d/%m/%Y"))
            data.append(record.value)

        datasets = [
            {
                "label": "Mon indice de performance réputationnelle",
                "backgroundColor": "rgb(255, 99, 132)",
                "borderColor": "rgb(255, 99, 132)",
                "data": data,
            }
        ]

        return {
            "page_data": {
                "labels": labels,
                "datasets": datasets,
            },
        }


def is_sorted(seq, *, key=None):
    if key is None:

        def key(x):
            return x

    return all(key(a) <= key(b) for a, b in pairwise(seq))
