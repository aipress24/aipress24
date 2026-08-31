# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Détection des changements d'un événement — `NOT-11`.

Fonctions pures : deux photographies des champs surveillés, avant et
après recopie dans le miroir public, et la description de ce qui a
bougé. Aucune base, aucune horloge.

La liste des champs surveillés a été corrigée le 2026-08-31 :
`pays_zip_ville` ne porte que le **pays** (`"FRA"`), le lieu vit dans
`pays_zip_ville_detail` (`"FRA / 75001 Paris"`). Surveiller le premier
seul serait resté muet sur « Paris → Lyon », le cas même pour lequel la
règle existe.
"""

from __future__ import annotations

import arrow
import pytest

from app.modules.events.change_detection import (
    WATCHED,
    describe_state,
    has_changed,
)


def _snap(**kw):
    base = dict.fromkeys(WATCHED)
    base.update(kw)
    return base


class TestWatchedFields:
    def test_the_place_is_watched_not_only_the_country(self) -> None:
        assert "pays_zip_ville_detail" in WATCHED
        assert "pays_zip_ville" in WATCHED

    def test_dates_and_address_are_watched(self) -> None:
        for field in ("start_datetime", "end_datetime", "address"):
            assert field in WATCHED


class TestHasChanged:
    """La détection dit **qu'**il y a eu un changement ; la description
    dit ce qu'il en est **maintenant**. Un delta ne survivrait pas au
    regroupement, qui remplace la notification précédente.
    """

    def test_no_change_says_nothing(self) -> None:
        snap = _snap(address="1 rue Test")
        assert has_changed(snap, dict(snap)) is False

    def test_a_city_change_is_announced(self) -> None:
        """Le cas paradigmatique, que l'ancienne liste ratait."""
        before = _snap(pays_zip_ville_detail="FRA / 75001 Paris")
        after = _snap(pays_zip_ville_detail="FRA / 69001 Lyon")

        assert has_changed(before, after) is True
        assert any("Lyon" in line for line in describe_state(after))

    def test_a_date_change_names_both_dates(self) -> None:
        before = _snap(start_datetime=arrow.get("2026-03-12T18:00:00+01:00"))
        after = _snap(start_datetime=arrow.get("2026-03-19T18:00:00+01:00"))

        assert has_changed(before, after) is True
        assert any("19/03/2026" in line for line in describe_state(after))

    def test_dates_are_described_in_paris_time(self) -> None:
        """Un membre lit une heure locale, pas de l'UTC."""
        before = _snap(start_datetime=arrow.get("2026-03-12T23:30:00+00:00"))
        after = _snap(start_datetime=arrow.get("2026-03-13T23:30:00+00:00"))

        # 23:30 UTC, c'est 00:30 le lendemain à Paris.
        assert has_changed(before, after) is True
        assert any("14/03/2026" in line for line in describe_state(after))

    def test_the_same_instant_written_differently_is_not_a_change(self) -> None:
        """Sans cela, chaque ré-enregistrement du formulaire posterait
        une notification à tous les accrédités."""
        before = _snap(start_datetime=arrow.get("2026-03-12T18:00:00+01:00"))
        after = _snap(start_datetime=arrow.get("2026-03-12T17:00:00+00:00"))

        assert has_changed(before, after) is False

    def test_several_fields_produce_several_lines(self) -> None:
        before = _snap(address="1 rue A", pays_zip_ville_detail="FRA / 75001 Paris")
        after = _snap(address="2 rue B", pays_zip_ville_detail="FRA / 69001 Lyon")

        assert has_changed(before, after) is True

    @pytest.mark.parametrize(
        ("before_val", "after_val"),
        [(None, "1 rue A"), ("1 rue A", None)],
    )
    def test_appearing_and_disappearing_values_both_count(
        self, before_val, after_val
    ) -> None:
        before = _snap(address=before_val)
        after = _snap(address=after_val)

        assert has_changed(before, after) is True

    def test_blank_variations_are_not_a_change(self) -> None:
        assert has_changed(_snap(address=""), _snap(address="   ")) is False

    def test_an_unwatched_field_is_invisible_here(self) -> None:
        """Corriger une faute dans le contenu ne doit alerter personne.

        Les deux photographies portent un `contenu` **différent** :
        sans cela le test comparait deux instantanés identiques et
        n'aurait pas vu une détection élargie à toutes les clés
        présentes — un refactor tentant, qui ferait notifier à chaque
        correction de coquille.
        """
        before = _snap(address="1 rue A", start_datetime=None)
        after = _snap(address="1 rue A", start_datetime=None)

        # `contenu` n'est pas dans WATCHED : même si les deux
        # photographies en portaient un différent, rien ne bougerait.
        before["contenu"] = "avant"
        after["contenu"] = "après"

        assert has_changed(before, after) is False


class TestTheMessageSurvivesMerging:
    """Un delta ne survit pas au regroupement.

    Le service remplace la notification précédente quand une seconde
    arrive dans la fenêtre. Un message qui dit « la date passe de X à
    Y » serait donc effacé par un message qui dit « l'adresse passe de
    A à B », et le membre n'entendrait jamais parler de la date. Un
    état final est vrai quel que soit le nombre de fusions.
    """

    def test_the_description_does_not_depend_on_what_changed(self) -> None:
        final = _snap(
            start_datetime=arrow.get("2026-03-19T18:00:00+01:00"),
            address="2 rue B",
            pays_zip_ville_detail="FRA / 69001 Lyon",
        )

        # Deux chemins différents vers le même état final.
        after_a_date_change = describe_state(final)
        after_an_address_change = describe_state(final)

        assert after_a_date_change == after_an_address_change
        joined = " ".join(after_a_date_change)
        assert "19/03/2026" in joined
        assert "2 rue B" in joined
        assert "Lyon" in joined

    def test_empty_fields_are_left_out(self) -> None:
        """Un « Adresse : — » n'apprend rien à personne."""
        lines = describe_state(
            _snap(address="", pays_zip_ville_detail="FRA / 75001 Paris")
        )

        assert len(lines) == 1
        assert "Paris" in lines[0]
