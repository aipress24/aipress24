# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from wtforms import BooleanField, StringField

from ..base import Step
from ..form import BaseForm


class Form1(BaseForm):
    # Group: competences
    analyser_mon_secteur = BooleanField("Analyse de mon secteur")
    vision_strategique = BooleanField(
        "Définir et donner une vision stratégique de mon organisation"
    )
    diriger_des_equipes = BooleanField("Diriger des équipes")
    mener_des_projets = BooleanField("Mener des projets")
    financer_des_projets = BooleanField("Financer des projets")
    communiquer_avec_les_medias = BooleanField("Communiquer avec les médias")
    conception_production_contenus = BooleanField(
        "Conception, production de contenus (écrit, audio, vidéo)"
    )
    evenements_conferences = BooleanField(
        "Participation et animation en tant qu’Expert à des événements / conférences"
    )
    gestion_de_crises = BooleanField("Pilotage ou participation à la gestion de crises")
    communication_de_crise = BooleanField("Communication de crise")
    enseignement_formation = BooleanField("Enseignement/Formation")
    lobbying = BooleanField("Lobbying")
    sponsoring_culturel_ou_sportif = BooleanField(
        "Sponsoring d’événements culturels ou sportifs"
    )
    sponsoring_technologique = BooleanField(
        "Sponsoring technologique pour chercheurs et startups"
    )
    partage_bonnes_pratiques = BooleanField(
        "Partage de bonnes pratiques (RSE, pro, techniques, etc.)"
    )

    # Group: experiences
    experience_1 = StringField("Expérience 1")
    experience_2 = StringField("Expérience 2")
    experience_3 = StringField("Expérience 3")
    experience_4 = StringField("Expérience 4")
    experience_5 = StringField("Expérience 5")

    # Group: formations
    formation_1 = StringField("Formation 1")
    formation_2 = StringField("Formation 2")
    formation_3 = StringField("Formation 3")
    formation_4 = StringField("Formation 4")
    formation_5 = StringField("Formation 5")

    # Group: logiciels
    logiciel_1 = StringField("Logiciel 1")
    logiciel_2 = StringField("Logiciel 2")
    logiciel_3 = StringField("Logiciel 3")
    logiciel_4 = StringField("Logiciel 4")
    logiciel_5 = StringField("Logiciel 5")

    # Group: langues
    langue_1 = StringField("Langue 1")
    langue_2 = StringField("Langue 2")
    langue_3 = StringField("Langue 3")
    langue_4 = StringField("Langue 4")
    langue_5 = StringField("Langue 5")

    class Meta:
        groups = [
            {
                "label": "Compétences",
                "fields": [
                    "analyser_mon_secteur",
                    "vision_strategique",
                    "diriger_des_equipes",
                    "mener_des_projets",
                    "financer_des_projets",
                    "communiquer_avec_les_medias",
                    "conception_production_contenus",
                    "evenements_conferences",
                    "gestion_de_crises",
                    "communication_de_crise",
                    "enseignement_formation",
                    "lobbying",
                    "sponsoring_culturel_ou_sportif",
                    "sponsoring_technologique",
                    "partage_bonnes_pratiques",
                ],
            },
            {
                "label": "Expériences professionnelles",
                "fields": [
                    "experience_1",
                    "experience_2",
                    "experience_3",
                    "experience_4",
                    "experience_5",
                ],
            },
            {
                "label": "Formations",
                "fields": [
                    "formation_1",
                    "formation_2",
                    "formation_3",
                    "formation_4",
                    "formation_5",
                ],
            },
            {
                "label": "Logiciels maîtrisés",
                "fields": [
                    "logiciel_1",
                    "logiciel_2",
                    "logiciel_3",
                    "logiciel_4",
                    "logiciel_5",
                ],
            },
            {
                "label": "Langues maîtrisées",
                "fields": [
                    "langue_1",
                    "langue_2",
                    "langue_3",
                    "langue_4",
                    "langue_5",
                ],
            },
        ]


class Step5I(Step):
    title = "Inscription sur Aipress24 (5/6)"
    subtitle = "Formations, compétences, expériences"
    form_class = Form1
    next_step_id = "step6-i"
    prev_step_id = "step4-i"
