# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""L'analyse d'une liste d'adresses saisie à la main — 2026-09-02.

Deux vues en avaient chacune leur version, et elles ne découpaient pas
pareil : le partage d'article acceptait l'espace comme séparateur et
validait la forme de l'adresse, l'achat d'une consultation offerte non.
Le désaccord tombait sur un chemin **facturé** — un destinataire de plus
ou de moins, c'est une ligne de plus ou de moins sur la facture.
"""

from __future__ import annotations

import pytest

from app.modules.wire.services.recipients import parse_recipient_emails


class TestLesSeparateurs:
    """Virgule, retour à la ligne, espace : indifféremment."""

    @pytest.mark.parametrize(
        "saisie",
        [
            "a@b.com,c@d.com",
            "a@b.com\nc@d.com",
            "a@b.com c@d.com",
            "a@b.com , c@d.com",
            "a@b.com,\n  c@d.com\n",
        ],
    )
    def test_deux_adresses_quelle_que_soit_la_ponctuation(self, saisie) -> None:
        assert parse_recipient_emails(saisie) == ["a@b.com", "c@d.com"]

    def test_l_espace_separait_dans_une_version_et_pas_dans_l_autre(self) -> None:
        """Le cas qui divergeait : côté achat, « a@b.com c@d.com » ne
        faisait qu'une chaîne, invalide et facturée comme un seul
        destinataire."""
        assert len(parse_recipient_emails("a@b.com c@d.com")) == 2


class TestCeQuiEstEcarte:
    @pytest.mark.parametrize(
        "saisie", ["", "   ", "\n,\n", "pas-une-adresse", "sans@point", "@b.com"]
    )
    def test_rien_qui_ressemble_a_une_adresse_ne_passe(self, saisie) -> None:
        assert parse_recipient_emails(saisie) == []

    def test_le_valide_survit_a_l_invalide(self) -> None:
        """Une ligne fautive ne doit pas emporter la liste entière."""
        assert parse_recipient_emails("bon@ex.com, nawak, autre@ex.com") == [
            "autre@ex.com",
            "bon@ex.com",
        ]


class TestLaNormalisation:
    def test_les_doublons_ne_comptent_qu_une_fois(self) -> None:
        """Sinon le même destinataire est facturé deux fois."""
        assert parse_recipient_emails("A@B.com, a@b.com, a@B.COM") == ["a@b.com"]

    def test_la_casse_ne_compte_pas(self) -> None:
        assert parse_recipient_emails("Jean.Dupont@Example.COM") == [
            "jean.dupont@example.com"
        ]

    def test_l_ordre_est_stable(self) -> None:
        """Un `set` rendait un ordre variable d'un appel à l'autre — la
        facture et le courriel n'énuméraient pas pareil."""
        saisie = "z@ex.com, a@ex.com, m@ex.com"

        assert parse_recipient_emails(saisie) == parse_recipient_emails(saisie)
        assert parse_recipient_emails(saisie) == ["a@ex.com", "m@ex.com", "z@ex.com"]
