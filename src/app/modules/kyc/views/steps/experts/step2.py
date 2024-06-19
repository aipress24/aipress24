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
    ("f1", "Fondateur"),
    ("f3", "Président"),
    ("f2", "Directeur"),
    ("f4", "Directeur général"),
    ("f5", "Directeur général adjoint"),
    ("f3", "Chercheur"),
    ("f4", "Enseignant / chercheur"),
    ("f5", "Enseignant"),
    ("f4", "Consultant"),
    ("f5", "Formateur"),
    ("f6", "Ministre"),
    ("f7", "Secrétaire d'Etat"),
    ("f8", "Député"),
    ("f9", "Sénateur"),
    ("f10", "Conseiller régional"),
    ("f11", "Conseiller départemental"),
    ("f12", "Maire"),
    ("f13", "Adjoint au maire"),
    ("f14", "Conseiller municipal"),
    ("f15", "Autre élu"),
    ("f9", "Député européen"),
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


# Je suis Expert.e salarié.e dans une organisation
# Je suis Expert.e et je suis en charge des relations presse dans mon organisation
# Je dirige une startup
# Je suis Expert.e indépendant.e


class Step2X1(Step):
    title = "Inscription sur Aipress24 (2/6)"
    subtitle = "Expert.e salarié.e dans une organisation"
    form_class = Form1

    next_step_id = "step3-x1-1"
    prev_step_id = "step1"


class Step2X2(Step):
    title = "Inscription sur Aipress24 (2/6)"
    subtitle = "Expert.e en charge des relations presse dans mon organisation"
    form_class = Form1

    next_step_id = "step3-x1-1"
    prev_step_id = "step1"


class Step2X3(Step):
    title = "Inscription sur Aipress24 (2/6)"
    subtitle = "Je dirige une startup"
    form_class = Form1

    next_step_id = "step3-x1-1"
    prev_step_id = "step1"


class Step2X4(Step):
    title = "Inscription sur Aipress24 (2/6)"
    subtitle = "Expert.e indépendant.e"
    form_class = Form1

    next_step_id = "step3-x1-1"
    prev_step_id = "step1"
