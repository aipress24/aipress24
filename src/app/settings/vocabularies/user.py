# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

# Source: "Statuts.ods"
# Ou:https://trello.com/c/2VLVi3ao/21
"""
Stagiaire: Membre étudiant qui, quelle que soit sa communauté d’appartenance
(journalistes, communicants, développeurs, leaders), effectue un stage.

Débutant: Membre qui vient d’arriver sur la plate-forme

Validé: Membre dont l’inscription est validée par AiPRESS24

Certifié: Membre officiellement reconnu par son employeur au travers de la page
commerciale Entreprise d’AiPRESS24.

Star: Membre qui reçoit les applaudissements de la part des communautés dans
son écosystème. Ce statut est attribué automatiquement par le système de
réputation d’AiPRESS24

Premium: Membre qui paie pour accéder à différents services

Elite: Membre qui fait partie des plus gros acheteurs de prestations ou
d’articles que les fournisseurs apprécient particulièrement. C'est le système
de réputation d’AiPRESS24 qui donne ce statut.
"""

from __future__ import annotations

USER_STATUS = [
    "Stagiaire",
    "Débutant",
    "Validé",
    "Certifié",
    "Star",
    "Premium",
    "Elite",
]
