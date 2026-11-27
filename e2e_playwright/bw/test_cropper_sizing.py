# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""The image cropper takes the size of its container once it shows (bug #0412).

The croppers sit in Alpine `x-show` blocks, so the cropper can start while
its container is still hidden. The test loads the Vite bundle the site
serves (the e2e server serves the dev assets, which the suite blocks).
"""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page

ROOT = Path(__file__).resolve().parents[2]

PAGE = """
<div id="block" style="display: none">
  <div style="width: 800px; height: 300px"><img id="image"></div>
</div>
"""

START_CROPPER = """
() => new Promise((ready) => {
    const canvas = document.createElement("canvas");
    canvas.width = 2000;
    canvas.height = 500;
    const image = document.getElementById("image");
    image.src = canvas.toDataURL();
    window.cropper = new Cropper(image, { aspectRatio: 4, viewMode: 2, ready });
})
"""


def test_the_cropper_fills_a_container_shown_after_it_started(page: Page):
    [bundle] = (ROOT / "vite" / "dist" / "assets").glob("index-*.js")
    page.set_content(PAGE)
    page.add_script_tag(path=bundle, type="module")
    page.wait_for_function("window.Cropper !== undefined")

    page.evaluate(START_CROPPER)
    assert page.evaluate("cropper.getContainerData().width") == 200

    page.evaluate("document.getElementById('block').style.display = 'block'")

    page.wait_for_function("cropper.getContainerData().width === 800")
    assert page.evaluate("cropper.getContainerData().height") == 300
