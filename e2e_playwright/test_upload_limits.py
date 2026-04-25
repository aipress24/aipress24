# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Upload size limits — **mutating, prod-skipped**.

Tests the BW gallery upload at 1 / 5 / 30 / 50 MB to validate :
- 1-30 MB pass cleanly,
- 50 MB is rejected with a clean Werkzeug 413 (after the
  `MAX_CONTENT_LENGTH` config wiring), not a silent nginx timeout.

Skipped on production via the `block_mutations_on_prod` autouse
fixture in `conftest.py`.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image
from playwright.sync_api import Page

# (label, target size in bytes, expected_outcome)
SIZE_CASES = [
    ("1MB", 1 * 1024 * 1024, "ok"),
    ("5MB", 5 * 1024 * 1024, "ok"),
    ("30MB", 30 * 1024 * 1024, "ok"),
    ("50MB", 50 * 1024 * 1024, "rejected"),
]


def _make_jpeg(size_bytes: int) -> bytes:
    """Build a JPEG of approximately `size_bytes`. Uses a noisy
    pattern so JPEG can't compress it to a few KB."""
    # Heuristic : ~3 bytes per pixel for high-entropy JPEG. Round up.
    pixels = max(int((size_bytes / 3) ** 0.5), 64)
    img = Image.new("RGB", (pixels, pixels))
    # Random-ish pattern ; PIL can't import os.urandom directly into
    # an image, so we cheat with a tiled gradient that compresses badly.
    px = img.load()
    for y in range(pixels):
        for x in range(pixels):
            px[x, y] = (
                (x * 7 + y * 11) & 0xFF,
                (x * 13 + y * 17) & 0xFF,
                (x * 19 + y * 23) & 0xFF,
            )
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    out = buf.getvalue()
    # Pad with trailing comments to hit the target size if necessary.
    if len(out) < size_bytes:
        out = out + b"\xff\xfe" + b"X" * (size_bytes - len(out) - 4) + b"\xff\xd9"
    return out


@pytest.mark.parametrize(
    ("label", "size_bytes", "expected"),
    SIZE_CASES,
    ids=[c[0] for c in SIZE_CASES],
)
def test_bw_gallery_upload(
    page: Page,
    base_url: str,
    profile,
    login,
    label: str,
    size_bytes: int,
    expected: str,
    tmp_path,
) -> None:
    """Upload a JPEG of the given size to the BW gallery."""
    p = profile("PRESS_MEDIA")
    login(p)

    # Locate the BW gallery upload form. The exact path depends on the
    # user's BW activation state ; if no gallery surface is reachable
    # for this profile, skip.
    resp = page.goto(f"{base_url}/BW/configure-gallery", wait_until="domcontentloaded")
    if resp is None or resp.status >= 400:
        pytest.skip(f"no gallery surface reachable for {p['email']}")

    file_path = tmp_path / f"{label}.jpg"
    file_path.write_bytes(_make_jpeg(size_bytes))

    # Locate the file input ; broad selector since the markup may evolve.
    file_inputs = page.locator('input[type="file"]')
    if file_inputs.count() == 0:
        pytest.skip("no file input in the gallery form")

    file_inputs.first.set_input_files(str(file_path))
    page.click('button[type="submit"], input[type="submit"]')

    if expected == "ok":
        # Page should not show a 413 / nginx error.
        body = page.locator("body").inner_text().lower()
        assert "413" not in body and "request entity too large" not in body, (
            f"{label} upload was rejected unexpectedly"
        )
    else:
        body = page.locator("body").inner_text().lower()
        assert ("413" in body or "request entity too large" in body), (
            f"{label} upload should have been rejected with 413"
        )
