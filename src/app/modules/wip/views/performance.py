# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""WIP performance page."""

from __future__ import annotations

from itertools import pairwise

from flask import g, render_template

from app.modules.wip import blueprint

from ._common import get_secondary_menu


@blueprint.route("/performance")
def performance():
    """Performance"""
    # Lazy import to avoid circular import
    from app.services.reputation import get_reputation_history

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

    page_data = {
        "labels": labels,
        "datasets": datasets,
    }

    return render_template(
        "wip/pages/performance.j2",
        title="Suivre ma performance réputationnelle",
        page_data=page_data,
        menus={"secondary": get_secondary_menu("performance")},
    )


def is_sorted(seq, *, key=None):
    """Check if a sequence is sorted."""
    if key is None:

        def key(x):
            return x

    return all(key(a) <= key(b) for a, b in pairwise(seq))
