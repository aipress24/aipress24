# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from wtforms import PasswordField, SelectField, StringField, validators

from ..base import Step
from ..common import CIVILITE_CHOICES
from ..form import BaseForm

FONCTION_CHOICES = [
    ("", "Choisissez votre fonction"),
    ("f1", "Développeur"),
    ("f2", "Architecte"),
    ("f3", "Chef de projet"),
    ("f4", "Product owner"),
    ("f5", "Scrum master"),
    ("f6", "DevOps"),
    ("f7", "Data engineer"),
    ("f8", "Data analyst"),
    ("f9", "Data scientist"),
    ("f10", "Designer"),
    ("f11", "Autre"),
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
    fonction = SelectField(
        "Fonction",
        choices=FONCTION_CHOICES,
        validators=[validators.InputRequired()],
    )
    email = StringField(
        "E-mail professionnel",
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
                    "fonction",
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


class Step2I1(Step):
    title = "Inscription sur Aipress24 (2/6)"
    subtitle = "IT Transformer salarié.e d’une organisation"
    form_class = Form1

    next_step_id = "step3-i1-1"
    prev_step_id = "step1"


class Step2I2(Step):
    title = "Inscription sur Aipress24 (2/6)"
    subtitle = (
        "IT Transformer salarié.e et je suis en charge des relations presse dans mon"
        " organisation"
    )
    form_class = Form1

    next_step_id = "step3-i1-1"
    prev_step_id = "step1"


class Step2I3(Step):
    title = "Inscription sur Aipress24 (2/6)"
    subtitle = " IT Transformer indépendant.e"
    form_class = Form1

    next_step_id = "step3-i1-1"
    prev_step_id = "step1"
