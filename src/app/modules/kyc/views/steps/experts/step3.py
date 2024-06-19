# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from wtforms import StringField, validators

from ..base import Step
from ..form import BaseForm


class Form1(BaseForm):
    # Group: employeur
    groupe = StringField(
        "Nom du groupe",
        [validators.Length(max=64)],
    )
    entreprise = StringField(
        "Nom de l’entreprise",
        [validators.InputRequired(), validators.Length(max=64)],
    )
    adresse_professionnelle = StringField(
        "Adresse professionnelle",
        [validators.InputRequired(), validators.Length(max=64)],
    )
    complement_adresse = StringField(
        "Complément d’adresse",
        [validators.Length(max=64)],
    )
    code_postal = StringField(
        "Code postal",
        [validators.InputRequired(), validators.Length(max=64)],
    )
    ville = StringField(
        "Ville",
        [validators.InputRequired(), validators.Length(max=64)],
    )
    pays = StringField(
        "Pays",
        [validators.InputRequired(), validators.Length(max=64)],
    )
    telephone = StringField(
        "Téléphone (Standard)",
        [validators.InputRequired(), validators.Length(max=64)],
    )
    site_web = StringField(
        "Site Web",
        [validators.Length(max=64)],
    )

    class Meta:
        groups = [
            {
                "label": "Informations employeur",
                "fields": [
                    "groupe",
                    "entreprise",
                    "adresse_professionnelle",
                    "complement_adresse",
                    "code_postal",
                    "ville",
                    "pays",
                    "telephone",
                    "site_web",
                ],
            },
        ]


class Step3_X1_1(Step):
    title = "Inscription sur Aipress24 (3/6)"
    subtitle = "Expert"
    form_class = Form1

    next_step_id = "step4-x"
    prev_step_id = "step2-x1"
