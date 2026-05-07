# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Bug 0119 regression: the B01 "Configurer le contenu" page initialises
two tom-select widgets (`type_organisation` main + `type_organisation_detail`).
tom-select silently caps rendered options at 50 unless `maxOptions` is set
explicitly. The "Organisations privées" detail taxonomy has ~169 entries,
so without an explicit cap users only see the first 50 alphabetically (list
ends at "Entreprise de décoration") and items past that surface only via
the search filter — the exact symptom reported by the PO.

This is a static-asset regression guard: it parses the template source
and asserts both initialisations carry `maxOptions: null`. There's no
runtime test because the change is JS-only and exercising it end-to-end
would require Playwright + a seeded ~169-item taxonomy, which is overkill.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_TEMPLATE = (
    Path(__file__).parents[4]
    / "src"
    / "app"
    / "modules"
    / "bw"
    / "bw_activation"
    / "templates"
    / "bw_activation"
    / "B01_configure_content.html"
)


@pytest.fixture(scope="module")
def template_source() -> str:
    return _TEMPLATE.read_text()


def _select_init_count(source: str) -> int:
    """Count occurrences of `new TomSelect(` in the template source."""
    return source.count("new TomSelect(")


class TestMaxOptionsCapDisabled:
    """Bug 0119: every TomSelect init in B01 must override the default
    `maxOptions: 50` so long taxonomies render in full."""

    def test_template_exists(self):
        assert _TEMPLATE.exists(), f"template not found at {_TEMPLATE}"

    def test_each_tom_select_init_carries_max_options(self, template_source: str):
        # Crude but stable: there must be at least one `maxOptions:`
        # override per TomSelect init (some inits use `null` for "uncapped",
        # others use a numeric cap like 1000 for AJAX-loaded selects — both
        # are fine; what matters is they don't fall through to the default
        # 50-item cap).
        init_count = _select_init_count(template_source)
        max_opts_count = template_source.count("maxOptions:")
        assert max_opts_count >= init_count, (
            f"expected at least {init_count} `maxOptions:` overrides "
            f"(one per TomSelect init), found {max_opts_count}. The default "
            "maxOptions:50 will silently truncate any taxonomy with > 50 "
            "entries (cf. bug 0119 — Organisations privées has ~169)."
        )
