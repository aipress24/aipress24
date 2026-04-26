# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Werkzeug ``MAX_CONTENT_LENGTH`` boundary check.

Targets the dedicated diagnostic endpoint ``/tests/upload`` (drains
the body and reports back, no DB write — safe on prod). This
verifies the regression we fixed at commit ``b4e6b248`` : without
``app.config['MAX_CONTENT_LENGTH']`` wired, a 50 MB upload would
silently time out at nginx instead of producing a clean Flask 413.

Two cases :
- A small upload succeeds and the page reports the bytes received.
- An oversized upload is rejected with a 413.

Both are read-only with respect to application state.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect

# Sized to bracket the production ``MAX_CONTENT_LENGTH`` (32 MB) :
SMALL_BYTES = 1 * 1024 * 1024     # well under the limit
OVERSIZED_BYTES = 64 * 1024 * 1024  # well over


def test_small_upload_is_accepted(
    page: Page,
    base_url: str,
    profile,
    login,
    tmp_path,
) -> None:
    """A small file POSTed to /tests/upload is read end-to-end."""
    p = profile("PRESS_MEDIA")
    login(p)

    file_path = tmp_path / "small.bin"
    file_path.write_bytes(b"x" * SMALL_BYTES)

    page.goto(f"{base_url}/tests/upload", wait_until="domcontentloaded")
    page.set_input_files('input[type="file"]', str(file_path))
    page.click('button[type="submit"]')

    expect(page.locator("body")).to_contain_text("Upload reçu")


def test_oversized_upload_is_rejected_with_413(
    page: Page,
    base_url: str,
    profile,
    login,
    tmp_path,
) -> None:
    """An upload above MAX_CONTENT_LENGTH is rejected by Werkzeug
    (HTTP 413), not silently dropped at the proxy."""
    p = profile("PRESS_MEDIA")
    login(p)

    file_path = tmp_path / "huge.bin"
    file_path.write_bytes(b"x" * OVERSIZED_BYTES)

    page.goto(f"{base_url}/tests/upload", wait_until="domcontentloaded")
    page.set_input_files('input[type="file"]', str(file_path))
    with page.expect_response(
        lambda r: r.url.endswith("/tests/upload") and r.request.method == "POST",
        timeout=60_000,
    ) as info:
        page.click('button[type="submit"]')
    resp = info.value
    assert resp.status == 413, (
        f"Oversized upload to /tests/upload should return 413, got "
        f"{resp.status} — MAX_CONTENT_LENGTH likely not wired."
    )
