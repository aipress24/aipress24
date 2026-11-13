# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Bug 0238: on the "Gérer les rôles internes" modals, the Flowbite
``dark:*`` variants rendered as an illegible dark slate whenever the OS was in
dark mode. The cause was the Tailwind Play CDN, whose default is
``darkMode: 'media'``.

The BW pages now take their CSS from the Vite build only, which uses
``darkMode: 'class'``: ``dark:*`` applies under a ``.dark`` ancestor, which
these pages never set. The visual rendering is not asserted here.
"""

from __future__ import annotations

from pathlib import Path

from app.modules.bw import bw_activation

REPO_ROOT = Path(__file__).parents[4]


def test_bw_layout_does_not_load_the_tailwind_play_cdn() -> None:
    layout = Path(bw_activation.__file__).parent / "templates" / "layout.html"

    assert "cdn.tailwindcss.com" not in layout.read_text(encoding="utf-8")


def test_the_css_build_ignores_the_os_dark_mode() -> None:
    config = (REPO_ROOT / "vite" / "tailwind.config.js").read_text(encoding="utf-8")

    assert "darkMode: 'class'" in config
