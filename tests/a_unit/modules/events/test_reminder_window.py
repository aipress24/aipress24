# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""La fenêtre du rappel J−1 — `NOT-13`, fonction pure.

« Envoyé J−1 à 09:00 heure de Paris » se lit **au plus tôt** 09:00, pas
**exactement** 09:00 : une tâche horaire qui ne déclenche qu'à l'heure
juste perd une journée entière de rappels dès qu'un tour est manqué.
Avec « au plus tôt », le tour de 10:00 rattrape, et le registre
d'envoi rend tous les suivants inertes.

Le fuseau est explicite parce que le planificateur ne l'est pas :
`BlockingScheduler()` est construit sans `timezone=`, donc un crontab
« 0 9 * * * » déclencherait à 11:00 à Paris sur un serveur en UTC.
"""

from __future__ import annotations

import arrow

from app.modules.events.reminders import reminder_date


class TestReminderDate:
    def test_nothing_before_nine_in_paris(self) -> None:
        assert reminder_date(arrow.get("2026-03-12T07:59:00+01:00")) is None

    def test_from_nine_onwards(self) -> None:
        at_nine = arrow.get("2026-03-12T09:00:00+01:00")
        assert reminder_date(at_nine) == arrow.get("2026-03-13").date()

    def test_late_ticks_still_catch_up(self) -> None:
        """Un tour manqué à 09:00 se rattrape à 23:00 — le registre
        empêche le doublon, pas l'heure."""
        late = arrow.get("2026-03-12T23:00:00+01:00")
        assert reminder_date(late) == arrow.get("2026-03-13").date()

    def test_the_hour_is_read_in_paris_not_utc(self) -> None:
        """08:00 UTC en été, c'est 10:00 à Paris : le rappel est dû.

        C'est la non-régression du serveur en UTC : lu en UTC, ce même
        instant serait « avant 09:00 » et ne déclencherait rien.
        """
        summer = arrow.get("2026-07-15T08:00:00+00:00")
        assert reminder_date(summer) == arrow.get("2026-07-16").date()

    def test_just_before_nine_paris_in_utc_terms(self) -> None:
        assert reminder_date(arrow.get("2026-07-15T06:00:00+00:00")) is None

    def test_late_evening_rolls_to_the_next_paris_day(self) -> None:
        """23:30 UTC le 12, c'est 00:30 le 13 à Paris : le rappel porte
        alors sur le 14, pas sur le 13."""
        assert reminder_date(arrow.get("2026-03-12T23:30:00+00:00")) is None
        assert reminder_date(arrow.get("2026-03-13T08:30:00+00:00")) == (
            arrow.get("2026-03-14").date()
        )
