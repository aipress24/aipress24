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

import re
from pathlib import Path

from app.modules.bw import bw_activation

REPO_ROOT = Path(__file__).parents[4]


def test_bw_layout_does_not_load_the_tailwind_play_cdn() -> None:
    layout = Path(bw_activation.__file__).parent / "templates" / "layout.html"

    assert "cdn.tailwindcss.com" not in layout.read_text(encoding="utf-8")


def test_the_built_css_ignores_the_os_dark_mode() -> None:
    """Class mode compiles `dark:` utilities to `:is(.dark *)` selectors;
    media mode would put them in a `prefers-color-scheme` query."""
    (stylesheet,) = (REPO_ROOT / "vite" / "dist" / "assets").glob("*.css")
    css = stylesheet.read_text(encoding="utf-8")
    media_blocks = re.findall(r"@media \(prefers-color-scheme: ?dark\)\{(.*?)\}\}", css)

    assert r".dark\:" in css
    assert ":is(.dark *)" in css
    assert all(r".dark\:" not in block for block in media_blocks)
