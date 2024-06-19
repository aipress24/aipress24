# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from wtforms import BooleanField, StringField

from ..base import Step
from ..form import BaseForm


class Form1(BaseForm):
    # Group: competences

    conception_production_de_contenus_ecrit_audio_video = BooleanField(
        "Conception, production de contenus (écrit, audio, vidéo)",
    )
    briefer_les_redacteurs_photographes_videastes_illustrateurs = BooleanField(
        "Briefer les rédacteurs, photographes, vidéastes, illustrateurs…",
    )
    conception_organisation_evenements_presse = BooleanField(
        "Conception et organisation d’événements de presse",
    )
    conception_organisation_evenements_pro_et_grand_public = BooleanField(
        "Conception et organisation d’événements pro et grand public",
    )
    conception_strategie_communication = BooleanField(
        "Conception de stratégie de communication",
    )
    campagnes_relations_presse = BooleanField(
        "Campagnes de Relations Presse",
    )
    campagnes_relations_publics = BooleanField(
        "Campagnes de Relations Publics",
    )
    communication_de_crise = BooleanField(
        "Communication de crise",
    )
    animer_table_ronde_conference = BooleanField(
        "Animer une table ronde / conférence",
    )
    media_training = BooleanField(
        "Média Training",
    )
    enseignement_formation = BooleanField(
        "Enseignement/Formation",
    )
    utiliser_ia_generatives = BooleanField(
        "Utiliser des IA génératives",
    )
    analyse_gestion_reputation = BooleanField(
        "Analyse et gestion de la réputation",
    )
    animation_communautes_reseaux_sociaux = BooleanField(
        "Animation de communautés / Réseaux sociaux",
    )
    communication_externe = BooleanField(
        "Communication externe",
    )
    communication_interne = BooleanField(
        "Communication interne",
    )
    brand_content = BooleanField(
        "Brand Content",
    )
    lobbying = BooleanField(
        "Lobbying",
    )
    gestion_projet_web = BooleanField(
        "Gestion de projet Web",
    )
    gestion_projet_innovation = BooleanField(
        "Gestion de projet d’innovation",
    )
    gestion_plateau_audiovisuel = BooleanField(
        "Gestion de plateau audiovisuel",
    )
    organisation_portage_produits = BooleanField(
        "Organisation de portage de produits dans les rédactions",
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
                    "concevoir_et_gerer_la_ligne_editoriale_du_media",
                    "rediger_des_articles",
                    "reportage_photo",
                    "reportage_audio",
                    "reportage_video",
                    "montage",
                    "illustration",
                    "animer_une_table_ronde_conference",
                    "media_coaching",
                    "enseignement",
                    "utiliser_des_ia_generatives",
                    "data_science",
                    "dataviz",
                    "gestion_de_projet_web",
                    "gestion_de_projet_d_innovation",
                    "gestion_de_plateau_audiovisuel",
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


class Step5C(Step):
    title = "Inscription sur Aipress24 (5/6)"
    subtitle = "Formations, compétences, expériences"
    form_class = Form1
    next_step_id = "step6-c"
    prev_step_id = "step4-c"
