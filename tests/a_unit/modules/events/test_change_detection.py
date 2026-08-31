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

from app.modules.events.change_detection import WATCHED, describe_changes


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


class TestDescribeChanges:
    def test_no_change_says_nothing(self) -> None:
        snap = _snap(address="1 rue Test")
        assert describe_changes(snap, dict(snap)) == []

    def test_a_city_change_is_announced(self) -> None:
        """Le cas paradigmatique, que l'ancienne liste ratait."""
        before = _snap(pays_zip_ville_detail="FRA / 75001 Paris")
        after = _snap(pays_zip_ville_detail="FRA / 69001 Lyon")

        lines = describe_changes(before, after)

        assert len(lines) == 1
        assert "Paris" in lines[0]
        assert "Lyon" in lines[0]

    def test_a_date_change_names_both_dates(self) -> None:
        before = _snap(start_datetime=arrow.get("2026-03-12T18:00:00+01:00"))
        after = _snap(start_datetime=arrow.get("2026-03-19T18:00:00+01:00"))

        lines = describe_changes(before, after)

        assert len(lines) == 1
        assert "12/03/2026" in lines[0]
        assert "19/03/2026" in lines[0]

    def test_dates_are_described_in_paris_time(self) -> None:
        """Un membre lit une heure locale, pas de l'UTC."""
        before = _snap(start_datetime=arrow.get("2026-03-12T23:30:00+00:00"))
        after = _snap(start_datetime=arrow.get("2026-03-13T23:30:00+00:00"))

        lines = describe_changes(before, after)

        # 23:30 UTC, c'est 00:30 le lendemain à Paris.
        assert "13/03/2026" in lines[0]
        assert "14/03/2026" in lines[0]

    def test_the_same_instant_written_differently_is_not_a_change(self) -> None:
        """Sans cela, chaque ré-enregistrement du formulaire posterait
        une notification à tous les accrédités."""
        before = _snap(start_datetime=arrow.get("2026-03-12T18:00:00+01:00"))
        after = _snap(start_datetime=arrow.get("2026-03-12T17:00:00+00:00"))

        assert describe_changes(before, after) == []

    def test_several_fields_produce_several_lines(self) -> None:
        before = _snap(address="1 rue A", pays_zip_ville_detail="FRA / 75001 Paris")
        after = _snap(address="2 rue B", pays_zip_ville_detail="FRA / 69001 Lyon")

        assert len(describe_changes(before, after)) == 2

    @pytest.mark.parametrize(
        ("before_val", "after_val"),
        [(None, "1 rue A"), ("1 rue A", None)],
    )
    def test_appearing_and_disappearing_values_both_count(
        self, before_val, after_val
    ) -> None:
        before = _snap(address=before_val)
        after = _snap(address=after_val)

        assert len(describe_changes(before, after)) == 1

    def test_blank_variations_are_not_a_change(self) -> None:
        assert describe_changes(_snap(address=""), _snap(address="   ")) == []

    def test_an_unwatched_field_is_invisible_here(self) -> None:
        """Corriger une faute dans le contenu ne doit alerter personne."""
        before = _snap(address="1 rue A")
        after = _snap(address="1 rue A")

        assert describe_changes(before, after) == []
