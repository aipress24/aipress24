# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from wtforms import SelectMultipleField, StringField, validators

from ..base import Step
from ..form import BaseForm

PRESSE_CHOICES = [
    ("p1", "Presse d’information générale"),
    ("p2", "Presse culturelle"),
    ("p3", "Presse économique et financière"),
    ("p4", "Presse professionnelle"),
    ("p5", "Presse grand public spécialisée"),
    ("p6", "Presse sportive"),
]


class Form1(BaseForm):
    # Group: zones
    zone_1 = StringField("Zone 1", [validators.Length(max=64)])
    zone_2 = StringField("Zone 2", [validators.Length(max=64)])
    zone_3 = StringField("Zone 3", [validators.Length(max=64)])
    zone_4 = StringField("Zone 4", [validators.Length(max=64)])

    # Group: specialisation
    presse = SelectMultipleField(
        "Si vous êtes étudiant en journalisme, pour quel type de presse travaillez-vous"
        " déjà ?",
        choices=PRESSE_CHOICES,
        validators=[validators.InputRequired()],
    )
    matieres = StringField(
        "Quelles matières étudiez-vous ?", [validators.InputRequired()]
    )

    # Group: engagement
    syndicat_1 = StringField(
        "Je fais partie d’un syndicat ou d’un club professionnel (1)",
        [validators.Length(max=64)],
    )
    nom_organisation_1 = StringField(
        "Voici le nom de cette organisation", [validators.Length(max=64)]
    )
    position_organisation_1 = StringField(
        "Voici ma position dans cette organisation", [validators.Length(max=64)]
    )

    syndicat_2 = StringField(
        "Je fais partie d’un syndicat ou d’un club professionnel (2)",
        [validators.Length(max=64)],
    )
    nom_organisation_2 = StringField(
        "Voici le nom de cette organisation", [validators.Length(max=64)]
    )
    position_organisation_2 = StringField(
        "Voici ma position dans cette organisation", [validators.Length(max=64)]
    )

    syndicat_3 = StringField(
        "Je fais partie d’un syndicat ou d’un club professionnel (3)",
        [validators.Length(max=64)],
    )
    nom_organisation_3 = StringField(
        "Voici le nom de cette organisation", [validators.Length(max=64)]
    )
    position_organisation_3 = StringField(
        "Voici ma position dans cette organisation", [validators.Length(max=64)]
    )

    class Meta:
        groups = [
            {
                "label": "Zones géographiques",
                "fields": [
                    "zone_1",
                    "zone_2",
                    "zone_3",
                    "zone_4",
                ],
            },
            {
                "label": "Spécialisation",
                "fields": [
                    "presse",
                    "matieres",
                ],
            },
            {
                "label": "Engagement professionnel, syndical ou associatif",
                "fields": [
                    "syndicat_1",
                    "nom_organisation_1",
                    "position_organisation_1",
                    "syndicat_2",
                    "nom_organisation_2",
                    "position_organisation_2",
                    "syndicat_3",
                    "nom_organisation_3",
                    "position_organisation_3",
                ],
            },
        ]


class Step4E(Step):
    title = "Inscription sur Aipress24 (4/6)"
    subtitle = "Centres d'intérêt"
    form_class = Form1
    next_step_id = "step5-e"
    prev_step_id = "step3-e"
