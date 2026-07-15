# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Bug 0238: the BW activation layout loads the Tailwind Play CDN, whose
default ``darkMode: 'media'`` lit up the Flowbite ``dark:*`` variants on the
"Gérer les rôles internes" modals as an illegible dark slate whenever the OS
was in dark mode. The fix pins the CDN to ``darkMode: 'class'`` (matching the
project's Vite build), so those variants only apply under a ``.dark`` ancestor
— which the BW pages never set.

This is a regression guard: it fails if the config pin is removed. The actual
visual rendering is not asserted (it can't be, without a browser).
"""

from __future__ import annotations

from pathlib import Path

from app.modules.bw import bw_activation


def test_bw_layout_pins_tailwind_darkmode_to_class() -> None:
    layout = Path(bw_activation.__file__).parent / "templates" / "layout.html"
    content = layout.read_text(encoding="utf-8")
    assert 'darkMode: "class"' in content, (
        "the BW layout must pin the Play CDN to darkMode:'class' so the "
        "Flowbite dark: variants don't fire on OS dark mode (bug 0238)"
    )
