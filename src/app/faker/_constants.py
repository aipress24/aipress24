# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

# flake8: noqa

from __future__ import annotations

ORGANISATIONS = [
    "Libération",
    "Le Monde",
    "La voix du Nord",
    "Les DNA",
    "Voiles et voiliers",
    "Micro Hebdo",
    "Le Gorafi",
    "TF1",
    "Antenne 2",
    "FR3",
    "La Cinq",
    "Le journal de Mickey",
    "Picsou Magazine",
    "SVM",
    "Elektor",
    "60 millions d'amis",
]
ROLES = [
    "Journaliste",
    "Pigiste",
    "Rédacteur/trice en chef",
    "Rédacteur/trice en chef adjoint(e)",
    "Chef(fe) de rubrique",
    "Chef(fe) de service",
]

POST_CATEGORIES = [
    "Lifestyle",
    "Politique",
    "Sport",
    "Faits-divers",
    "Société",
    "Science",
]

POST_IMAGES = [
    "https://images.unsplash.com/photo-1483825366482-1265f6ea9bc9?ixid=MnwxMjA3fDB8MHxzZWFyY2h8NDJ8fGNsaW1hdGV8ZW58MHx8MHx8&ixlib=rb-1.2.1&auto=format&fit=crop&w=800&q=60",
    "https://images.unsplash.com/photo-1551866442-64e75e911c23?ixid=MnwxMjA3fDB8MHxzZWFyY2h8MTd8fGZyYW5jZXxlbnwwfHwwfHw%3D&ixlib=rb-1.2.1&auto=format&fit=crop&w=800&q=60",
    "https://images.unsplash.com/photo-1595435934249-5df7ed86e1c0?ixid=MnwxMjA3fDB8MHxzZWFyY2h8Mzh8fHRlbm5pc3xlbnwwfHwwfHw%3D&ixlib=rb-1.2.1&auto=format&fit=crop&w=800&q=60",
    "https://images.unsplash.com/photo-1606787620819-8bdf0c44c293?ixid=MnwxMjA3fDF8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8&ixlib=rb-1.2.1&auto=format&fit=crop&w=1350&q=80",
    "https://images.unsplash.com/photo-1629711748551-8a488e8bf69c?ixid=MnwxMjA3fDB8MHx0b3BpYy1mZWVkfDI5fHRvd0paRnNrcEdnfHxlbnwwfHx8fA%3D%3D&ixlib=rb-1.2.1&auto=format&fit=crop&w=500&q=60",
    "https://images.unsplash.com/photo-1548289161-f1088e9f559f?ixid=MnwxMjA3fDB8MHx0b3BpYy1mZWVkfDcyfHRvd0paRnNrcEdnfHxlbnwwfHx8fA%3D%3D&ixlib=rb-1.2.1&auto=format&fit=crop&w=500&q=60",
    "https://images.unsplash.com/photo-1600585154363-67eb9e2e2099?ixid=MnwxMjA3fDB8MHx0b3BpYy1mZWVkfDEzfHJuU0tESHd3WVVrfHxlbnwwfHx8fA%3D%3D&ixlib=rb-1.2.1&auto=format&fit=crop&w=500&q=60",
    "https://images.unsplash.com/photo-1574958269340-fa927503f3dd?ixid=MnwxMjA3fDB8MHx0b3BpYy1mZWVkfDE5fHJuU0tESHd3WVVrfHxlbnwwfHx8fA%3D%3D&ixlib=rb-1.2.1&auto=format&fit=crop&w=500&q=60",
    "https://images.unsplash.com/photo-1630673470267-417e4d361129?ixid=MnwxMjA3fDB8MHx0b3BpYy1mZWVkfDE1fGFldTZyTC1qNmV3fHxlbnwwfHx8fA%3D%3D&ixlib=rb-1.2.1&auto=format&fit=crop&w=500&q=60",
    "https://images.unsplash.com/photo-1587545694326-6359f26f3dcc?ixid=MnwxMjA3fDB8MHx0b3BpYy1mZWVkfDE5fGFldTZyTC1qNmV3fHxlbnwwfHx8fA%3D%3D&ixlib=rb-1.2.1&auto=format&fit=crop&w=500&q=60",
    "https://images.unsplash.com/photo-1512820790803-83ca734da794?ixid=MnwxMjA3fDB8MHx0b3BpYy1mZWVkfDI3fGFldTZyTC1qNmV3fHxlbnwwfHx8fA%3D%3D&ixlib=rb-1.2.1&auto=format&fit=crop&w=500&q=60",
    "https://images.unsplash.com/photo-1630673507885-1754499d2d03?ixid=MnwxMjA3fDB8MHx0b3BpYy1mZWVkfDI5fGFldTZyTC1qNmV3fHxlbnwwfHx8fA%3D%3D&ixlib=rb-1.2.1&auto=format&fit=crop&w=500&q=60",
    "https://images.unsplash.com/photo-1630673195489-1237053bab5e?ixid=MnwxMjA3fDB8MHx0b3BpYy1mZWVkfDMyfGFldTZyTC1qNmV3fHxlbnwwfHx8fA%3D%3D&ixlib=rb-1.2.1&auto=format&fit=crop&w=500&q=60",
    "https://images.unsplash.com/photo-1529586073768-05e0b5a65696?ixid=MnwxMjA3fDB8MHx0b3BpYy1mZWVkfDQ3fGFldTZyTC1qNmV3fHxlbnwwfHx8fA%3D%3D&ixlib=rb-1.2.1&auto=format&fit=crop&w=500&q=60",
    "https://images.unsplash.com/photo-1584276433286-8e64bebdc502?ixid=MnwxMjA3fDB8MHx0b3BpYy1mZWVkfDYxfGFldTZyTC1qNmV3fHxlbnwwfHx8fA%3D%3D&ixlib=rb-1.2.1&auto=format&fit=crop&w=500&q=60",
    "https://images.unsplash.com/photo-1620266751671-a453e4f50b91?ixid=MnwxMjA3fDB8MHx0b3BpYy1mZWVkfDY2fGFldTZyTC1qNmV3fHxlbnwwfHx8fA%3D%3D&ixlib=rb-1.2.1&auto=format&fit=crop&w=500&q=60",
    "https://images.unsplash.com/photo-1630091003936-aea522c1e8c3?ixid=MnwxMjA3fDB8MHx0b3BpYy1mZWVkfDk1fGFldTZyTC1qNmV3fHxlbnwwfHx8fA%3D%3D&ixlib=rb-1.2.1&auto=format&fit=crop&w=500&q=60",
]

COVER_IMAGES = [
    "https://images.unsplash.com/photo-1444628838545-ac4016a5418a?ixid=MXwxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHw%3D&ixlib=rb-1.2.1&auto=format&fit=crop&w=1950&h=200&q=80",
    "https://images.unsplash.com/photo-1637825891028-564f672aa42c?ixlib=rb-1.2.1&ixid=MnwxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8&auto=format&fit=crop&w=2670&h=200&q=80",
    "https://images.unsplash.com/photo-1637808947243-e21c44ba0422?ixlib=rb-1.2.1&ixid=MnwxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8&auto=format&fit=crop&w=2670&h=200&q=80",
    "https://images.unsplash.com/photo-1637776895052-86e559e887b4?ixlib=rb-1.2.1&ixid=MnwxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8&auto=format&fit=crop&w=2670&h=200&q=80",
    "https://images.unsplash.com/photo-1637778352878-f0b46d574a04?ixlib=rb-1.2.1&ixid=MnwxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8&auto=format&fit=crop&w=1374&h=200&q=80",
]

LOCATION = [
    "Paris",
    "Berlin",
    "Londres",
    "Rome",
    "Milan",
    "Rogent-le-Rotrou",
]
