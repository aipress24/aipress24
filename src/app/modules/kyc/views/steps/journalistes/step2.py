# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from ..base import Step
from ..common import CIVILITE_CHOICES
from ..fields import BooleanField, PasswordField, SelectField, StringField, validators
from ..form import BaseForm

FONCTION_CHOICES = [
    ("", "Choisissez votre fonction"),
    ("f1", "Journaliste"),
    ("f2", "Rédacteur en chef"),
    ("f3", "Secrétaire de rédaction"),
    ("f4", "Chef de rubrique"),
    ("f5", "Reporter"),
    ("f6", "Correspondant"),
    ("f7", "Photographe"),
    ("f8", "Vidéaste"),
    ("f9", "Infographiste"),
    ("f10", "Maquettiste"),
    ("f11", "Documentaliste"),
    ("f12", "Iconographe"),
    ("f13", "Webmaster"),
    ("f14", "Autre"),
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
    presse_ecrite_et_en_ligne = BooleanField("Presse écrite et en ligne")
    radio = BooleanField("Radio")
    television = BooleanField("Télévision")
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
                    "presse_ecrite_et_en_ligne",
                    "radio",
                    "television",
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


class Step2J1(Step):
    title = "Inscription sur Aipress24 (2/6)"
    subtitle = "Journaliste avec carte de presse"
    form_class = Form1

    next_step_id = "step3-j1-1"
    prev_step_id = "step1"


class Step2J2(Step):
    title = "Inscription sur Aipress24 (2/6)"
    subtitle = "Journaliste sans carte de presse"
    form_class = Form1

    next_step_id = "step3-j1-1"
    prev_step_id = "step1"


class Step2J3(Step):
    title = "Inscription sur Aipress24 (2/6)"
    subtitle = "Journaliste d'entreprise"
    form_class = Form1

    next_step_id = "step3-j1-1"
    prev_step_id = "step1"
