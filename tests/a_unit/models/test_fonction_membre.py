# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Présenter un membre par sa fonction — ticket #0325, règles `FCT-01` et
`FCT-02` de `local-notes/specs/fonction-membre.md`.

Fonctions pures sur des objets non persistés : aucune base, aucune
requête. Le cas nominal est celui du ticket — Martine Lefebure, présentée
comme « Dirigeant.e d'une Entreprise de Services et Conseils en
Transformation des Organisations » alors qu'elle a déclaré être
présidente.
"""

from __future__ import annotations

from app.models.auth import KYCProfile, User
from app.modules.swork.components.members_list import FilterByJobTitle


def _profil(fonctions: dict | None = None, label: str = "") -> KYCProfile:
    profile = KYCProfile(match_making=fonctions or {})
    profile.profile_label = label
    return profile


class TestLaFonctionAffichee:
    def test_le_cas_du_ticket(self) -> None:
        """FCT-01 — la première fonction déclarée, sans sa famille."""
        profile = _profil(
            {
                "fonctions_org_priv_detail": [
                    "DIRECTION GÉNÉRALE / Président.e",
                    "DIRECTION COMMERCIALE / Responsable commercial",
                ]
            },
            label="Dirigeant.e d’une Entreprise de Services et Conseils",
        )

        assert profile.fonction == "Président.e"

    def test_une_fonction_sans_famille_passe_telle_quelle(self) -> None:
        profile = _profil({"fonctions_journalisme": ["Rédacteur.trice en chef"]})

        assert profile.fonction == "Rédacteur.trice en chef"

    def test_le_journalisme_passe_avant_le_reste(self) -> None:
        """L'ordre de `toutes_fonctions` n'est pas indifférent : sur
        AIpress24, la fonction journalistique est celle qui situe le
        membre."""
        profile = _profil(
            {
                "fonctions_journalisme": ["Grand reporter"],
                "fonctions_org_priv_detail": ["DIRECTION GÉNÉRALE / Président.e"],
            }
        )

        assert profile.fonction == "Grand reporter"

    def test_sans_fonction_declaree_rien(self) -> None:
        """La propriété ne ment pas : c'est `User` qui décide du repli."""
        assert _profil({}, label="Dirigeant.e ou élu.e").fonction == ""


class TestLeRepliSurLeLibelleKyc:
    """FCT-02 — 48 des 186 profils mesurés n'ont aucune fonction. Sans
    repli, un quart des cartes perdrait son sous-titre."""

    def test_un_membre_qui_a_declare_sa_fonction_la_montre(self) -> None:
        user = User(email="m@example.com")
        user.profile = _profil(
            {"fonctions_org_priv_detail": ["DIRECTION GÉNÉRALE / Président.e"]},
            label="Dirigeant.e d’une Entreprise de Services et Conseils",
        )

        assert user.fonction == "Président.e"

    def test_un_membre_sans_fonction_garde_ce_quil_a_aujourdhui(self) -> None:
        user = User(email="m@example.com")
        user.profile = _profil({}, label="Dirigeant.e ou élu.e")

        assert user.fonction == "Dirigeant.e ou élu.e"

    def test_un_membre_sans_profil_ne_casse_pas(self) -> None:
        """Les cartes s'affichent aussi pour un compte incomplet."""
        assert User(email="m@example.com").fonction == ""

    def test_job_title_ne_change_pas_de_sens(self) -> None:
        """FCT-05 — `job_title` alimente l'API, l'export, l'index de
        recherche et le filtre de l'annuaire, qui construit ses options
        en Python ici et interroge `profile_label` en SQL. Les faire
        diverger casserait le filtre en silence."""
        user = User(email="m@example.com")
        user.profile = _profil(
            {"fonctions_org_priv_detail": ["DIRECTION GÉNÉRALE / Président.e"]},
            label="Dirigeant.e d’une Entreprise de Services et Conseils",
        )

        assert user.job_title == "Dirigeant.e d’une Entreprise de Services et Conseils"
        assert user.job_title != user.fonction


class TestLeFiltreDeLAnnuaire:
    """§4 de la spéc — le piège qui a dicté `FCT-05`.

    `FilterByJobTitle` construit ses options en Python depuis l'attribut
    nommé par `selector`, et les cherche en SQL dans la colonne visée par
    `apply`. Rien ne relie les deux : les faire diverger ne lève aucune
    erreur, le filtre renvoie simplement toujours zéro résultat.
    """

    def test_le_selecteur_et_la_colonne_designent_la_meme_valeur(self) -> None:
        # Ce que le filtre lit sur un membre pour bâtir ses options...
        user = User(email="m@example.com")
        user.profile = _profil(
            {"fonctions_org_priv_detail": ["DIRECTION GÉNÉRALE / Président.e"]},
            label="Dirigeant.e d’une Entreprise de Services et Conseils",
        )
        option = getattr(user, FilterByJobTitle.selector)

        # ... doit être ce que la requête SQL cherchera en base.
        assert option == user.profile.profile_label
        assert "profile_label" in str(KYCProfile.profile_label)
