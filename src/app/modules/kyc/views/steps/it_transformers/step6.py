# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from wtforms import BooleanField, StringField, validators

from ..base import Step
from ..form import BaseForm


class Form1(BaseForm):
    # Group: hobbies
    hobby_1 = StringField("Hobbies 1", [validators.Length(max=64)])
    hobby_2 = StringField("Hobbies 2", [validators.Length(max=64)])
    hobby_3 = StringField("Hobbies 3", [validators.Length(max=64)])
    hobby_4 = StringField("Hobbies 4", [validators.Length(max=64)])
    hobby_5 = StringField("Hobbies 5", [validators.Length(max=64)])

    # Group: convivialite
    convivialite_1 = BooleanField(
        "J’accepte de partager un verre ou un repas avec un.e Journaliste membre "
        "d’Aipress24 qui vient faire un reportage dans ma ville."
    )
    convivialite_2 = BooleanField(
        "J’accepte d’héberger un.e Journaliste membre d’Aipress24 qui vient faire un"
        " reportage dans ma ville."
    )
    convivialite_3 = BooleanField(
        "J’accepte de prendre un verre ou de partager un repas avec un membre"
        " d’Aipress24."
    )

    class Meta:
        groups = [
            {
                "label": "Hobbies",
                "fields": [
                    "hobby_1",
                    "hobby_2",
                    "hobby_3",
                    "hobby_4",
                    "hobby_5",
                ],
            },
            {
                "label": "Convivialité",
                "fields": [
                    "convivialite_1",
                    "convivialite_2",
                    "convivialite_3",
                ],
            },
        ]


class Step6I(Step):
    title = "Inscription sur Aipress24 (6/6)"
    subtitle = "Hobbies et convivialité"
    form_class = Form1
    prev_step_id = "step5-i"
    next_step_id = ""
