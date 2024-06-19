# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from wtforms import IntegerField, PasswordField, SelectField, StringField, validators

from ..base import Step
from ..common import CIVILITE_CHOICES
from ..form import BaseForm

DIPLOME_CHOICES = [
    ("", "Choisissez votre diplôme préparé"),
    ("d1", "Bac"),
    ("d6", "Autre Bac +5"),
    ("d7", "BTS"),
    ("d8", "DUT"),
    ("d9", "Licence"),
    ("d10", "Master"),
    ("d11", "Doctorat"),
    ("d2", "Autre Bac +1"),
    ("d3", "Autre Bac +2"),
    ("d4", "Autre Bac +3"),
    ("d5", "Autre Bac +4"),
    ("d12", "Autre"),
]


class Form1(BaseForm):
    # Group: info perso
    prenom = StringField(
        "Prénom", [validators.InputRequired(), validators.Length(min=1, max=64)]
    )
    nom = StringField(
        "Nom", [validators.InputRequired(), validators.Length(min=1, max=64)]
    )
    pseudo = StringField(
        "Pseudo", [validators.InputRequired(), validators.Length(max=64)]
    )
    civilite = SelectField(
        "Civilité", choices=CIVILITE_CHOICES, validators=[validators.InputRequired()]
    )
    password = PasswordField("Mot de passe", [validators.Length(min=6, max=35)])

    # Group: info pro
    diplome = SelectField(
        "Diplôme préparé",
        choices=DIPLOME_CHOICES,
        validators=[validators.InputRequired()],
    )
    annee_cursus = IntegerField(
        "Année du cursus",
        [validators.InputRequired(), validators.NumberRange(min=1, max=5)],
    )
    annees_total = IntegerField(
        "Nombre total d'années d'études",
        [validators.InputRequired(), validators.NumberRange(min=1, max=10)],
    )
    email = StringField(
        "E-mail",
        [validators.InputRequired(), validators.Length(min=6, max=35)],
    )
    mobile = StringField(
        "Numéro de mobile",
        [validators.InputRequired(), validators.Length(min=6, max=35)],
    )

    # Groupe: réseaux sociaux
    x = StringField("X")
    linkedin = StringField("LikedIn")
    facebook = StringField("Facebook")
    instagram = StringField("Instagram")
    youtube = StringField("Youtube")
    tiktok = StringField("TikTok")
    twitch = StringField("Twitch")
    snapchat = StringField("Snapchat")
    whatsapp = StringField("Whatsapp")
    signal = StringField("Signal")
    pinterest = StringField("Pinterest")
    reddit = StringField("Reddit")
    quora = StringField("Quora")
    discord = StringField("Discord")
    telegram = StringField("Telegram")
    olvid = StringField("Olvid")
    mastodon = StringField("Mastodon")

    # Groupe:

    class Meta:
        groups = [
            {
                "label": "Informations personnelles (obligatoires)",
                "fields": [
                    "prenom",
                    "nom",
                    "pseudo",
                    "civilite",
                    "password",
                ],
            },
            {
                "label": "Informations professionnelles (obligatoires)",
                "fields": [
                    "diplome",
                    "annee_cursus",
                    "annees_total",
                    "email",
                    "mobile",
                ],
            },
            {
                "label": "Réseaux sociaux",
                "fields": [
                    "x",
                    "linkedin",
                    "facebook",
                    "instagram",
                    "youtube",
                    "tiktok",
                    "twitch",
                    "snapchat",
                    "whatsapp",
                    "signal",
                    "pinterest",
                    "reddit",
                    "quora",
                    "discord",
                    "telegram",
                    "olvid",
                    "mastodon",
                ],
            },
        ]


class Step2E1(Step):
    title = "Inscription sur Aipress24 (2/6)"
    subtitle = "Etudiant.e"
    form_class = Form1

    next_step_id = "step3-e"
    prev_step_id = "step1"
