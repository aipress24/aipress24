# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from wtforms import StringField, validators

from ..base import Step
from ..form import BaseForm


class Form1(BaseForm):
    # Group: employeur
    groupe_formation = StringField(
        "Groupe de formation",
        [validators.Length(max=64)],
    )
    organisme_formation = StringField(
        "Nom de l’organisme de formation",
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
        [validators.InputRequired(), validators.Length(max=64)],
    )

    class Meta:
        groups = [
            {
                "label": "Informations organisation",
                "fields": [
                    "groupe_formation",
                    "organisme_formation",
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


class Step3_E(Step):
    title = "Inscription sur Aipress24 (3/6)"
    subtitle = "Etudiant.e"
    form_class = Form1

    next_step_id = "step4-e"
    prev_step_id = "step2-e1"
