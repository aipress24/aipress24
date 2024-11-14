# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from attr import field, frozen

from app.flask.lib.pywire import Component, component


@component
@frozen
class DropdownMenu(Component):
    entry_groups: list = field(init=False)

    def get_entry_groups(self) -> list:
        # random_label = random.choice(["Publier", "Afficher", "Supprimer"])
        return [
            [
                {"label": "Voir", "url": "#", "index": 0},
            ],
            # [
            #     {"label": "Ajouter un nouveau", "url": "#", "index": 1},
            #     {"label": random_label, "url": "#", "index": 2},
            # ],
        ]
