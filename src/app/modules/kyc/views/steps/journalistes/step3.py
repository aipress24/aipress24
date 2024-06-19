# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from ..base import Step
from ..fields import StringField, validators
from ..form import BaseForm


class Form1(BaseForm):
    # Group: employeur
    groupe_edition = StringField("Groupe d’édition", [validators.Length(max=64)])
    nom_agence_presse_ou_media = StringField(
        "Nom de l’agence de presse ou du média", [validators.Length(max=64)]
    )
    adresse_professionnelle = StringField(
        "Adresse professionnelle",
        [validators.InputRequired(), validators.Length(max=64)],
    )
    complement_adresse = StringField(
        "Complément d’adresse", [validators.Length(max=64)]
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
                    "groupe_edition",
                    "nom_agence_presse_ou_media",
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


class Step3_J1_1(Step):
    title = "Inscription sur Aipress24 (3/6)"
    subtitle = "Journaliste"
    form_class = Form1

    next_step_id = "step4-j"
    prev_step_id = "step2-j1"
