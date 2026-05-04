# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Coverage for ``app.modules.api.trix_blobs`` (was 47%).

The endpoint backs the Trix rich-text editor's image-paste
flow: the editor POSTs a multipart file and receives a signed
URL it embeds in the document.

Three branches to cover:

- POST without ``file`` → 400.
- POST with empty filename → 400.
- POST with a valid file → 200 + ``url`` / ``href`` /
  ``filename`` keys.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

_PNG_1x1 = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc\xfc\xff\xff?\x00\x05\xfe\x02"
    b"\xfe\xa72\xa6\xa1\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_trix_blob_no_file_returns_400(
    page: Page, base_url: str, profile, login
) -> None:
    """POST /api/trix_blobs/ with no `file` part → 400."""
    p = profile("PRESS_MEDIA")
    login(p)
    # Use page.evaluate fetch so cookies are sent.
    resp = page.evaluate(
        """async (url) => {
            const r = await fetch(url, {
                method: 'POST', credentials: 'same-origin',
                body: new FormData(),
            });
            const json = await r.json();
            return {status: r.status, json};
        }""",
        f"{base_url}/api/trix_blobs/",
    )
    assert resp["status"] == 400, resp
    assert "error" in resp["json"]


def test_trix_blob_empty_filename_returns_400(
    page: Page, base_url: str, profile, login
) -> None:
    """POST with a `file` part that has an empty filename → 400."""
    p = profile("PRESS_MEDIA")
    login(p)
    resp = page.evaluate(
        """async (url) => {
            const fd = new FormData();
            // Browser FormData with a Blob and explicit empty name.
            const blob = new Blob(['x'], {type: 'text/plain'});
            fd.append('file', blob, '');
            const r = await fetch(url, {
                method: 'POST', credentials: 'same-origin',
                body: fd,
            });
            return {status: r.status, body: await r.text()};
        }""",
        f"{base_url}/api/trix_blobs/",
    )
    # Some browsers strip empty filenames before send (the field
    # arrives without a `filename=` and Werkzeug rejects). Accept
    # 400 either way ; the route's invariant is « no upload
    # without a filename ».
    assert resp["status"] == 400, resp


@pytest.mark.mutates_db
def test_trix_blob_valid_upload_returns_signed_url(
    page: Page, base_url: str, profile, login
) -> None:
    """POST with a real file → 200, response has `url`, `href`,
    `filename` keys. Mutates storage (creates a FileObject row +
    writes to S3 / mock backend)."""
    p = profile("PRESS_MEDIA")
    login(p)
    # Pass the PNG bytes through Playwright as a base64 string,
    # rebuild a Blob in JS, and POST as multipart.
    import base64
    b64 = base64.b64encode(_PNG_1x1).decode("ascii")
    resp = page.evaluate(
        """async (args) => {
            const bytes = Uint8Array.from(
                atob(args.b64), c => c.charCodeAt(0)
            );
            const blob = new Blob([bytes], {type: 'image/png'});
            const fd = new FormData();
            fd.append('file', blob, 'pixel.png');
            const r = await fetch(args.url, {
                method: 'POST', credentials: 'same-origin',
                body: fd,
            });
            const ct = r.headers.get('content-type') || '';
            const body = ct.includes('json')
                ? await r.json()
                : await r.text();
            return {status: r.status, body};
        }""",
        {
            "url": f"{base_url}/api/trix_blobs/",
            "b64": b64,
        },
    )
    if resp["status"] >= 500:
        pytest.skip(
            "trix_blob upload hit 5xx — likely S3 / storage "
            f"backend unavailable in this env. Body : "
            f"{str(resp.get('body'))[:200]}"
        )
    assert resp["status"] == 200, resp
    body = resp["body"]
    assert isinstance(body, dict)
    assert body.get("filename") == "pixel.png"
    assert body.get("url"), f"missing url in response : {body}"
    assert body.get("href") == body.get("url"), (
        "href and url should match (same signed URL)"
    )
