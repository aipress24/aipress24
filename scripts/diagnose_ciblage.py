#!/usr/bin/env python
# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Why does an avis d'enquête's ciblage screen show nobody? — #0348.

Run against the database that shows the problem:

    uv run python scripts/diagnose_ciblage.py [<avis id>]

It answers the three questions that separate the possible causes, and
reads nothing but counts — no personal data is printed.
"""

from __future__ import annotations

import sys
from collections import Counter

from app.flask.extensions import db
from app.flask.main import create_app
from app.modules.wip.models import AvisEnquete
from app.modules.wip.services.newsroom.expert_filter import ExpertFilterService


def _service(avis, state):
    service = ExpertFilterService(session={})
    service._avis_enquete = avis
    service._state = dict(state)
    return service


def main() -> int:
    app = create_app()
    with app.app_context():
        query = db.session.query(AvisEnquete)
        avis = (
            query.filter(AvisEnquete.id == int(sys.argv[1])).one_or_none()
            if len(sys.argv) > 1
            else query.first()
        )
        if avis is None:
            print("Aucun avis d'enquête trouvé.")
            return 1

        print(f"avis {avis.id} — secteur de l'avis : {avis.sector!r}")

        # 1. Le vivier est-il peuplé ?
        without = _service(avis, {})
        with_journalists = _service(avis, {"include_journalists": "on"})
        pool = without._get_all_experts()
        print(f"\n1. vivier hors presse : {len(pool)}")
        print(f"   vivier avec presse  : {len(with_journalists._get_all_experts())}")
        if not pool:
            print("   -> le vivier est vide : la cause est en amont des filtres.")
            return 0

        # 2. Les critères ont-ils des options à proposer ?
        sector = next(s for s in without._get_selectors() if s.id == "secteur")
        cascade = sector.get_dual_tom_choices_for_js()
        print(
            f"\n2. cascade secteur : {len(cascade['field1'])} catégorie(s), "
            f"{len(cascade['field2'])} secteur(s) détaillé(s)"
        )
        if not cascade["field2"]:
            print("   -> aucun secteur proposé : voir le point 3.")

        # 3. Les valeurs des profils se relient-elles à la taxonomie ?
        detail_map = sector._taxonomy_detail_map
        held: Counter[str] = Counter()
        for expert in pool:
            for value in expert.profile.secteurs_activite or []:
                held[value] += 1
        resolved = sum(1 for v in held if v.strip().lower() in detail_map)
        by_child = sum(
            1
            for v in held
            if v.strip().lower() not in detail_map
            and "/" in v
            and v.split("/", 1)[1].strip().lower() in detail_map
        )
        lost = len(held) - resolved - by_child
        print(f"\n3. valeurs de secteur portées par le vivier : {len(held)} distinctes")
        print(f"   reconnues telles quelles          : {resolved}")
        print(f"   reconnues par leur terme enfant   : {by_child}")
        print(f"   non reliées à la taxonomie        : {lost}")
        if lost > len(held) / 2:
            print(
                "   -> la majorité des profils portent des valeurs qu'aucune\n"
                "      entrée de la taxonomie courante ne rejoint : c'est la cause."
            )
            for value, count in held.most_common(5):
                mark = "  " if value.strip().lower() in detail_map else "??"
                print(f"      {mark} {value!r} ({count})")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
