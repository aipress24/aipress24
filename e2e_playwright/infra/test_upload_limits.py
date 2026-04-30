# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Werkzeug ``MAX_CONTENT_LENGTH`` + ``MAX_FORM_MEMORY_SIZE``
boundary checks.

Targets the dedicated diagnostic endpoint ``/tests/upload`` (drains
the body and reports back, no DB write — safe on prod) plus a
form-field POST against an authenticated endpoint.

Verified regressions :

- ``b4e6b248`` (#0106 amont) : without ``app.config['MAX_CONTENT_LENGTH']``
  wired, a 50 MB upload would silently time out at nginx instead of
  producing a clean Flask 413.
- ``MAX_FORM_MEMORY_SIZE`` (#0106 aval) : Werkzeug 3+ caps form
  fields at 500 KB by default. The cropper.js base64 data-URL flow
  (BW configure-content / configure-gallery / KYC photo) would 413
  on any image > ~370 KB once base64-encoded, even though the file
  itself was well under MAX_IMAGE_SIZE (4 MB). Fix : bumped to 12 MB.

All tests are read-only with respect to application state.
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


def test_large_form_field_is_accepted(
    page: Page,
    base_url: str,
    profile,
    login,
) -> None:
    """A ~1.5 MB form field (cropper.js base64 data-URL shape) is
    accepted post-fix.

    Regression test for bug #0106 : pre-fix, Werkzeug 3+ default
    ``MAX_FORM_MEMORY_SIZE`` (500 KB) rejected any data-URL form
    field bigger than ~370 KB once base64-encoded, even though the
    underlying image was well within MAX_IMAGE_SIZE (4 MB).

    We POST to ``/preferences/banner`` (existing test surface, takes
    a `copyright` form field — the copyright text is short in real
    use but the form parser doesn't care about field semantics, only
    field size). Pre-fix : 413. Post-fix : < 400.
    """
    p = profile("PRESS_MEDIA")
    login(p)
    page.goto(
        f"{base_url}/preferences/banner",
        wait_until="domcontentloaded",
    )
    # ~1.5 MB form field — bigger than the 500 KB Werkzeug default,
    # smaller than the 12 MB MAX_FORM_MEMORY_SIZE we set.
    big_field = "x" * (1_500_000)
    js_post = """async (args) => {
        const r = await fetch(args.url, {
            method: 'POST', credentials: 'same-origin',
            body: new URLSearchParams(args.data),
            headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        });
        return {status: r.status, url: r.url};
    }"""
    resp = page.evaluate(
        js_post,
        {
            "url": f"{base_url}/preferences/banner",
            "data": {"submit": "cancel", "copyright": big_field},
        },
    )
    assert resp["status"] < 400, (
        f"large form field POST : got {resp['status']} — "
        "MAX_FORM_MEMORY_SIZE likely back to Werkzeug's 500 KB "
        "default. Bump in src/app/settings/constants.py + main.py."
    )
    assert "/auth/login" not in resp["url"]
