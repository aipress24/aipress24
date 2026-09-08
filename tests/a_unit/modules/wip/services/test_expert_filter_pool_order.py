# Copyright (c) 2026, Abilian SAS & TCA
# SPDX-License-Identifier: AGPL-3.0-only

"""Bug #0344 — the ciblage pool was empty for every sector.

`_get_all_experts` composes two filters: the journalist exclusion and
the thematic pre-filter. The pre-filter falls back to the unfiltered
pool when fewer than `MIN_CANDIDATES` match the sector, so its fallback
has to be computed on the population that ends up on screen. Run after
the pre-filter, the exclusion could empty a pool that had just passed
the floor on journalists alone — and it did, on a base where journalists
outnumber the other communities.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from app.modules.wip.services.newsroom.avis_matching import MIN_CANDIDATES
from app.modules.wip.services.newsroom.expert_filter import ExpertFilterService

SECTOR = "Aéronautique"


def _expert(id: int, community: str, sector: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=id,
        last_login_at=datetime.now(UTC),
        profile=SimpleNamespace(
            profile_community=community, secteurs_activite=[sector]
        ),
    )


class _StubRepo:
    def __init__(self, users):
        self._users = users

    def list(self, active=True):  # mirrors UserRepository.list
        return self._users


def _service(users, *, include_journalists: bool) -> ExpertFilterService:
    service = ExpertFilterService(session={}, user_repo=_StubRepo(users))
    service._avis_enquete = SimpleNamespace(sector=SECTOR, ciblage_secteur_detailles="")
    service._state = {"include_journalists": "on"} if include_journalists else {}
    return service


def _pool():
    """Enough journalists on the sector to clear the floor on their own."""
    journalists = [_expert(i, "PRESS_MEDIA", SECTOR) for i in range(MIN_CANDIDATES + 3)]
    others = [
        _expert(100, "LEADERS_EXPERTS", "Environnement"),
        _expert(101, "TRANSFORMERS", "Environnement"),
        _expert(102, "COMMUNICANTS", "Environnement"),
    ]
    return journalists, others


def test_non_journalists_survive_a_sector_matched_only_by_journalists():
    journalists, others = _pool()

    pool = _service(journalists + others, include_journalists=False)._get_all_experts()

    assert pool, "le ciblage était vide quel que soit le secteur (#0344)"
    assert {e.id for e in pool} == {e.id for e in others}


def test_ticking_the_box_brings_the_journalists_back():
    journalists, others = _pool()

    pool = _service(journalists + others, include_journalists=True)._get_all_experts()

    assert {e.id for e in pool} >= {e.id for e in journalists}


def test_a_journalist_only_base_still_yields_nothing_without_the_box():
    """Not every empty screen is this bug: with no other community
    registered, an empty pool is the correct answer."""
    journalists, _ = _pool()

    pool = _service(journalists, include_journalists=False)._get_all_experts()

    assert pool == []
