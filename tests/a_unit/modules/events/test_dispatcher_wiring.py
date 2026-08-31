# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Les noms d'action, des deux côtés du répartiteur.

Le gabarit poste `{"action": "..."}` et la vue le compare à un
littéral. Rien ne liait les deux : renommer d'un seul côté fait tomber
le POST dans `case _: return ""`, qui répond 200 avec un corps vide.
HTMX remplace alors le bloc de statut par du vide et le bouton
disparaît, sans erreur nulle part.

Les tests du parcours appellent les méthodes privées — ce qui vérifie
leur logique et saute précisément ce lien.
"""

from __future__ import annotations

from pathlib import Path

import pytest

TEMPLATE = Path("src/app/modules/events/templates/pages/event--accreditation.j2")
VIEW = Path("src/app/modules/events/views/event_detail.py")

ACTIONS = ("request-accreditation", "withdraw-accreditation")


@pytest.mark.parametrize("action", ACTIONS)
def test_the_template_posts_a_name_the_view_answers(action: str) -> None:
    assert f'"action": "{action}"' in TEMPLATE.read_text(), f"gabarit : {action}"
    assert f'case "{action}"' in VIEW.read_text(), f"vue : {action}"


def test_the_old_toggle_action_is_gone_from_both_sides() -> None:
    """`toggle-participate` accréditait d'un clic. Le §8 demande sa
    disparition, pas sa mise en sommeil."""
    assert "toggle-participate" not in TEMPLATE.read_text()
    assert "toggle-participate" not in VIEW.read_text()
