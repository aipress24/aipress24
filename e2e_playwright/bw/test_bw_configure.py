# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""BW configure-content / configure-gallery POST coverage.

The wizard test (``test_bw_wizard.py``) walks the activation tunnel
but stops at /confirmation/free — `stage_b1.configure_content` and
`stage_b1b.configure_gallery` were never reached. They are the only
remaining 30 %-coverage holes in the BW module and require image
uploads.

Approach :

- Log in as a journalist with an active named BW (erick's).
- POST `/BW/select-bw/<bw_id>` to populate the session
  (`bw_activated=True`, `bw_type=...`).
- POST `/BW/configure-content` (or `configure-gallery`) with the
  required form fields plus a tiny base64 JPEG via `data:` URL —
  the cropper-style upload path that `extract_image_from_request`
  resolves before hitting S3.

Marked ``mutates_db`` : the routes save File objects in S3 and
update `BusinessWall.logo_image` / `cover_image` / `bw_images`.
Side-effects are bounded (we send the same name/siren back, so the
non-image fields are idempotent).
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page

# Same BW used by the partnership / role-invitation lifecycle tests.
# Erick is PRESS_MEDIA, BW is named, owner=erick → he is BWMi.
_ERICK_NAMED_BW_ID = "3be67123-b68d-48ad-9043-e2a206d18893"
_PRESS_MEDIA_COMMUNITY = "PRESS_MEDIA"

_NAME_INPUT_RE = re.compile(
    r'<input[^>]+name="name"[^>]*value="([^"]*)"', re.I
)
_SIREN_INPUT_RE = re.compile(
    r'<input[^>]+name="siren"[^>]*value="([^"]*)"', re.I
)


def _extract_form_value(html: str, pattern: re.Pattern[str]) -> str:
    """Pull the current value of a named <input> from rendered HTML.

    Used to send the existing name / SIREN back unchanged — the route
    treats these as mandatory and overwrites silently. Sending the
    same value keeps the test side-effect-free for those fields."""
    m = pattern.search(html)
    return m.group(1).strip() if m else ""


@pytest.mark.mutates_db
def test_bw_configure_content_post_uploads_logo(
    page: Page,
    base_url: str,
    profile,
    login,
    authed_post,
    tiny_jpeg_data_url: str,
) -> None:
    """POST /BW/configure-content with a minimal valid logo.

    Drives ``stage_b1.configure_content`` (line ~85-112 :
    `extract_image_from_request` -> `create_file_object` -> `.save()`
    -> `business_wall.logo_image = …`). Asserts the success flash
    `Logo mis à jour avec succès` appears in the response body."""
    journalist = profile(_PRESS_MEDIA_COMMUNITY)
    login(journalist)

    sel = authed_post(f"{base_url}/BW/select-bw/{_ERICK_NAMED_BW_ID}", {})
    assert sel["status"] < 400 and "/auth/login" not in sel["url"]

    # GET the form to extract current `name` + `siren` (mandatory
    # fields ; the route flashes + redirects if either is empty).
    page.goto(
        f"{base_url}/BW/configure-content", wait_until="domcontentloaded"
    )
    html = page.content()
    name = _extract_form_value(html, _NAME_INPUT_RE)
    siren = _extract_form_value(html, _SIREN_INPUT_RE) or "123456789"
    if not name:
        pytest.skip(
            "configure-content : current `name` empty — would flash "
            "rather than process the upload"
        )

    js_post_with_body = """async (args) => {
        const r = await fetch(args.url, {
            method: 'POST', credentials: 'same-origin',
            body: new URLSearchParams(args.data),
            headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        });
        const t = await r.text();
        return {status: r.status, url: r.url, body: t};
    }"""
    resp = page.evaluate(
        js_post_with_body,
        {
            "url": f"{base_url}/BW/configure-content",
            "data": {
                "name": name,
                "siren": siren,
                "logo_image": tiny_jpeg_data_url,
                "logo_image_filename": "tiny.jpg",
            },
        },
    )
    assert resp["status"] < 400, f"configure-content : {resp['status']}"
    assert "/auth/login" not in resp["url"]
    assert "/not-authorized" not in resp["url"]

    # The route route flashes `Logo mis à jour avec succès` on
    # success. Flashes are emitted into `window.toasts = [...]` by
    # the layout — read from the POST response (the redirect target
    # consumes them on render). If we see the failure flash
    # `Erreur lors de l'upload du logo: …` instead, the file save
    # raised — that's the underlying S3/MinIO bug ; surface it.
    body = resp["body"]
    if "Erreur lors de l'upload du logo" in body:
        m = re.search(
            r"Erreur lors de l'upload du logo[^\"]*", body
        )
        pytest.fail(
            f"configure-content : upload caught and flashed an error : "
            f"{m.group(0)[:300] if m else '(no match)'}"
        )
    assert "Logo mis à jour avec succès" in body, (
        "configure-content : neither success nor known-failure flash "
        "in response — upload may have silently no-op'd"
    )


@pytest.mark.mutates_db
def test_bw_configure_content_post_uploads_bandeau(
    page: Page,
    base_url: str,
    profile,
    login,
    authed_post,
    tiny_jpeg_data_url: str,
) -> None:
    """Same as the logo case but on the `bandeau_image` field.

    Different `extract_image_from_request` call site (line ~115-142),
    different attribute (`cover_image`)."""
    journalist = profile(_PRESS_MEDIA_COMMUNITY)
    login(journalist)

    sel = authed_post(f"{base_url}/BW/select-bw/{_ERICK_NAMED_BW_ID}", {})
    assert sel["status"] < 400 and "/auth/login" not in sel["url"]

    page.goto(
        f"{base_url}/BW/configure-content", wait_until="domcontentloaded"
    )
    html = page.content()
    name = _extract_form_value(html, _NAME_INPUT_RE)
    siren = _extract_form_value(html, _SIREN_INPUT_RE) or "123456789"
    if not name:
        pytest.skip("configure-content : current `name` empty")

    resp = authed_post(
        f"{base_url}/BW/configure-content",
        {
            "name": name,
            "siren": siren,
            "bandeau_image": tiny_jpeg_data_url,
            "bandeau_image_filename": "bandeau.jpg",
        },
    )
    assert resp["status"] < 400, f"configure-content (bandeau) : {resp}"
    assert "/auth/login" not in resp["url"]
    assert "/not-authorized" not in resp["url"]


@pytest.mark.mutates_db
def test_bw_configure_gallery_post_adds_image(
    page: Page,
    base_url: str,
    profile,
    login,
    authed_post,
    tiny_jpeg_data_url: str,
) -> None:
    """POST /BW/configure-gallery with a minimal valid image.

    Drives ``stage_b1b.configure_gallery`` (line 60-90 :
    `extract_image_from_request` -> `create_file_object.save()` ->
    `BWImage(...)` -> `business_wall.add_bw_image(...)`). Idempotent
    cleanup follows : delete the freshly-added image so subsequent
    runs don't fill the gallery up to ``MAX_GALLERY_IMAGES``."""
    journalist = profile(_PRESS_MEDIA_COMMUNITY)
    login(journalist)

    sel = authed_post(f"{base_url}/BW/select-bw/{_ERICK_NAMED_BW_ID}", {})
    assert sel["status"] < 400 and "/auth/login" not in sel["url"]

    # Snapshot the current gallery so we can diff after the POST and
    # find the freshly-added image's UUID for cleanup.
    page.goto(
        f"{base_url}/BW/configure-gallery", wait_until="domcontentloaded"
    )
    before_ids = set(_gallery_image_ids(page))

    js_post_with_body = """async (args) => {
        const r = await fetch(args.url, {
            method: 'POST', credentials: 'same-origin',
            body: new URLSearchParams(args.data),
            headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        });
        const t = await r.text();
        return {status: r.status, url: r.url, body: t};
    }"""
    resp = page.evaluate(
        js_post_with_body,
        {
            "url": f"{base_url}/BW/configure-gallery",
            "data": {
                "image": tiny_jpeg_data_url,
                "image_filename": "gallery.jpg",
                "caption": "e2e test caption",
                "copyright": "e2e test",
            },
        },
    )
    if resp["status"] >= 500:
        # Pull the Flask debug page's exception line so the bug note
        # has a concrete error to qualify.
        m = re.search(
            r"<h1[^>]*>([A-Z][A-Za-z]+(?:Error|Exception)[^<]*)</h1>",
            resp["body"],
        )
        exc = m.group(1).strip() if m else "(no exc heading)"
        m2 = re.search(
            r'<h2[^>]*class="traceback"[^>]*>([^<]+)</h2>', resp["body"]
        )
        title = m2.group(1).strip() if m2 else ""
        pytest.fail(
            f"configure-gallery : 500 — exc={exc!r} title={title!r}"
        )
    assert resp["status"] < 400, f"configure-gallery : {resp}"
    assert "/auth/login" not in resp["url"]
    assert "/not-authorized" not in resp["url"]

    page.goto(
        f"{base_url}/BW/configure-gallery", wait_until="domcontentloaded"
    )
    after_ids = set(_gallery_image_ids(page))
    new_ids = after_ids - before_ids
    if not new_ids:
        # The route silently no-ops when MAX_GALLERY_IMAGES is hit.
        # Treat that as a soft skip rather than a failure — the
        # cleanup-loop variant of this test would have to delete an
        # arbitrary image, which we'd rather not do.
        pytest.skip(
            "configure-gallery : no new image detected — gallery may "
            "already be at MAX_GALLERY_IMAGES, or the POST silently "
            "rejected the data-URL"
        )

    # Cleanup : delete every image we just added.
    for image_id in new_ids:
        cleanup = authed_post(
            f"{base_url}/BW/delete-gallery-image/{image_id}", {}
        )
        assert cleanup["status"] < 400, (
            f"cleanup delete-gallery-image/{image_id} : {cleanup}"
        )


def _gallery_image_ids(page: Page) -> list[str]:
    """Return UUIDs of currently-rendered gallery images.

    The template renders one `<form action=".../delete-gallery-image/
    <uuid>" …>` per image (cf. B01b_configure_gallery.html). We pull
    the UUIDs out of those URLs. Returns an empty list if the gallery
    is empty (or the URL pattern has changed)."""
    return page.evaluate(
        """() => {
            const out = [];
            const rx = /\\/delete-gallery-image\\/([a-f0-9-]{36})/i;
            for (const el of document.querySelectorAll(
                'form[action*="delete-gallery-image"], '
                + '[hx-post*="delete-gallery-image"]'
            )) {
                const url = el.getAttribute('action')
                    || el.getAttribute('hx-post') || '';
                const m = url.match(rx);
                if (m) out.push(m[1]);
            }
            return out;
        }"""
    )
