# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from wtforms import StringField, validators

from ..base import Step
from ..form import BaseForm


class Form1(BaseForm):
    # Group: secteurs
    secteur_1 = StringField("Secteur 1", [validators.Length(max=64)])
    secteur_2 = StringField("Secteur 2", [validators.Length(max=64)])
    secteur_3 = StringField("Secteur 3", [validators.Length(max=64)])
    secteur_4 = StringField("Secteur 4", [validators.Length(max=64)])

    # Group: zones
    zone_1 = StringField("Zone 1", [validators.Length(max=64)])
    zone_2 = StringField("Zone 2", [validators.Length(max=64)])
    zone_3 = StringField("Zone 3", [validators.Length(max=64)])
    zone_4 = StringField("Zone 4", [validators.Length(max=64)])

    # Group: engagement
    syndicat_1 = StringField(
        "Je fais partie d’un syndicat ou d’un club professionnel 1",
        [validators.Length(max=64)],
    )
    nom_organisation_1 = StringField(
        "Voici le nom de cette organisation", [validators.Length(max=64)]
    )
    position_organisation_1 = StringField(
        "Voici ma position dans cette organisation", [validators.Length(max=64)]
    )

    syndicat_2 = StringField(
        "Je fais partie d’un syndicat ou d’un club professionnel 2",
        [validators.Length(max=64)],
    )
    nom_organisation_2 = StringField(
        "Voici le nom de cette organisation", [validators.Length(max=64)]
    )
    position_organisation_2 = StringField(
        "Voici ma position dans cette organisation", [validators.Length(max=64)]
    )

    syndicat_3 = StringField(
        "Je fais partie d’un syndicat ou d’un club professionnel 3",
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
                "label": "Secteurs",
                "fields": [
                    "secteur_1",
                    "secteur_2",
                    "secteur_3",
                    "secteur_4",
                ],
            },
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


class Step4I(Step):
    title = "Inscription sur Aipress24 (4/6)"
    subtitle = "Centres d'intérêt"
    form_class = Form1
    next_step_id = "step5-i"
    prev_step_id = "step3-i1-1"
