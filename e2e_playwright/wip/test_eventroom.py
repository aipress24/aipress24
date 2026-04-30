# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""WIP eventroom — create + edit + image-upload coverage.

Existing tests :
- ``test_wip_lifecycle.py::test_publish_unpublish_toggle[event]`` —
  toggles the published flag on an existing event (assumes the
  journalist already owns one).
- ``test_wip_subpages.py`` — smokes GET on event sub-pages.

This file fills the write-path gap on the WIP eventroom :
creation of a brand-new event from the form, edition of its title,
image upload via the cropper data-URL path, and idempotent soft-
delete cleanup.

Drives ``EventsWipView`` (`crud/cbvs/events.py`) :
- ``post`` (line 159 of `_base.py`) for both create and edit
  branches (the same handler, distinguished by presence of `id`).
- ``images`` + ``_add_image`` (lines 226-296 of `events.py`).
- ``delete`` (line 256 of `_base.py`) for cleanup.

Important : the edit POST must include **every** field rendered in
the form, even those the user didn't touch. ``form.populate_obj``
overwrites the model with `field.data`, which is `None` for any
`TextAreaField`/`StringField` whose key is missing from the
formdata. NOT NULL columns then raise ``IntegrityError`` (e.g.
`chapo` on Event). The browser does this correctly because the
edit page renders the full form ; tests have to do the same.

Marked ``mutates_db`` : creates one Event row + one EventImage row,
then soft-deletes the event. The EventImage's S3 blob is not reaped
(no GC on the soft-delete path), but it's tiny and won't collide.
"""

from __future__ import annotations

import time

import pytest
from playwright.sync_api import Page

_PRESS_MEDIA_COMMUNITY = "PRESS_MEDIA"
_TITLE_PREFIX = "e2e-event-"


@pytest.mark.mutates_db
def test_wip_event_create_then_delete(
    page: Page,
    base_url: str,
    profile,
    login,
    authed_post,
    authed_get,
) -> None:
    """Create an event from the new-form, then soft-delete it.

    Steps :
    1. GET /wip/events/new — pull a valid `sector` + `event_type`
       value from the rendered RichSelectField wrapper (server-side
       choices live in the `x-data` attribute of the wrapper div).
    2. POST /wip/events/ with those values + a unique title.
    3. Find the new event in the listing → grab its id (string —
       snowflakes overflow `parseInt` precision).
    4. GET /wip/events/<id>/delete to soft-delete (cleanup).
    """
    journalist = profile(_PRESS_MEDIA_COMMUNITY)
    login(journalist)

    page.goto(
        f"{base_url}/wip/events/new", wait_until="domcontentloaded"
    )
    sector = _first_option_value(page, "sector")
    event_type = _first_option_value(page, "event_type")
    if not sector or not event_type:
        xdata = page.evaluate(
            """() => {
                const sel = document.querySelector('select[name="sector"]');
                if (!sel) return '(no select)';
                const wrapper = sel.closest('[x-data]');
                if (!wrapper) return '(no x-data wrapper)';
                return (wrapper.getAttribute('x-data') || '').slice(0, 800);
            }"""
        )
        pytest.fail(
            f"events/new : sector={sector!r} event_type={event_type!r} "
            f"— x-data of sector wrapper: {xdata!r}"
        )

    # Per-run unique title — runs with the same ontology values must
    # not collide with leftover rows from prior failed runs.
    title = f"{_TITLE_PREFIX}{int(time.time() * 1000) % 10**10}"
    contenu = "<p>Contenu généré par e2e_playwright/wip/test_eventroom.py</p>"

    create = authed_post(
        f"{base_url}/wip/events/",
        {
            "_action": "save",
            "titre": title,
            "chapo": "Chapô e2e",
            "contenu": contenu,
            "sector": sector,
            "event_type": event_type,
        },
    )
    assert create["status"] < 400, f"events POST create : {create}"
    assert "/auth/login" not in create["url"]
    # On success the post() handler redirects to the index. If we
    # stayed on POST /wip/events/ the form re-rendered with
    # validation errors — fail loudly so future ontology drift is
    # surfaced rather than swallowed by the listing scan below.
    assert create["url"].rstrip("/").endswith("/wip/events"), (
        f"events POST create stayed on form (validation error?) — "
        f"final URL: {create['url']}"
    )

    new_id = _find_event_id(page, base_url, title)
    assert new_id is not None, (
        f"created event with titre={title!r} not found in /wip/events/ "
        "listing — POST may have silently failed validation"
    )

    # Cleanup right away : `delete` is a GET that soft-deletes. Edit
    # path (POST `id=…`) is exercised by `test_wip_event_edit` below
    # — kept separate so a regression in update() doesn't leave a
    # zombie row from this test's create() succeeding.
    cleanup = authed_get(f"{base_url}/wip/events/{new_id}/delete")
    assert cleanup["status"] < 400, f"events delete : {cleanup}"


@pytest.mark.mutates_db
def test_wip_event_create_edit_delete(
    page: Page,
    base_url: str,
    profile,
    login,
    authed_post,
    authed_get,
) -> None:
    """Create an event, edit its title, then soft-delete.

    The edit POST scrapes the rendered edit form (every <input>,
    <textarea>, <select>) and re-submits it verbatim with only
    `titre` changed. That mirrors browser behaviour : the server
    relies on the browser to return all fields, otherwise
    `populate_obj` writes `None` to columns whose model has
    `default=""` (which only applies on INSERT, not UPDATE)."""
    journalist = profile(_PRESS_MEDIA_COMMUNITY)
    login(journalist)

    page.goto(
        f"{base_url}/wip/events/new", wait_until="domcontentloaded"
    )
    sector = _first_option_value(page, "sector")
    event_type = _first_option_value(page, "event_type")
    if not sector or not event_type:
        pytest.skip("events/new : ontology select empty")

    title = f"{_TITLE_PREFIX}edit-{int(time.time() * 1000) % 10**10}"
    create_payload = {
        "_action": "save",
        "titre": title,
        "chapo": "Chapô e2e edit",
        "contenu": "<p>Contenu initial</p>",
        "sector": sector,
        "event_type": event_type,
    }
    create = authed_post(f"{base_url}/wip/events/", create_payload)
    assert create["status"] < 400 and "/auth/login" not in create["url"]
    new_id = _find_event_id(page, base_url, title)
    assert new_id is not None, f"created event {title!r} not in listing"

    try:
        # Scrape the edit form — `populate_obj` will null out any
        # NOT NULL column whose key isn't in the formdata, so a
        # partial submission 500s. The browser submits the full form ;
        # so do we.
        # flask-classful mounts the default `edit(id)` method at
        # `/edit/<id>/` (action-first), not `/<id>/edit`. Custom
        # `@route("/<id>/delete")` for delete keeps the id-first form.
        page.goto(
            f"{base_url}/wip/events/edit/{new_id}/",
            wait_until="domcontentloaded",
        )
        full_form = _scrape_form_values(page)
        assert len(full_form) > 5, (
            f"edit form scrape returned only {len(full_form)} keys "
            f"({sorted(full_form.keys())}) — page may have 404'd or "
            "the form layout changed"
        )
        full_form["_action"] = "save"
        full_form["id"] = new_id
        edited_title = f"{title}-edited"
        full_form["titre"] = edited_title

        # Use page.evaluate(fetch) so we can read the response body
        # — `authed_post` only returns status + url, but we need to
        # inspect `window.toasts` to confirm the save flash appeared.
        edit = page.evaluate(
            """async (args) => {
                const r = await fetch(args.url, {
                    method: 'POST', credentials: 'same-origin',
                    body: new URLSearchParams(args.data),
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                });
                return {
                    status: r.status, url: r.url, body: await r.text(),
                };
            }""",
            {"url": f"{base_url}/wip/events/", "data": full_form},
        )
        assert edit["status"] < 400, (
            f"events POST edit : {edit['status']} — keys passed: "
            f"{sorted(full_form.keys())}"
        )
        assert "/auth/login" not in edit["url"]
        # On success, post() redirects to the index where the
        # "Enregistré" flash lands in `window.toasts` (JSON-escaped
        # to `Enregistr\\u00e9`). The page renders TWO `window.toasts`
        # blocks (one per layout level — public + private both
        # consume `get_flashed_messages()`), so we just check for the
        # escape sequence anywhere in the body. Validation failure
        # re-renders the form template — neither block has the flash.
        assert "Enregistr" in edit["body"], (
            "events POST edit : no `Enregistré` flash in response — "
            "validation likely failed silently."
        )
        page.goto(
            f"{base_url}/wip/events/", wait_until="domcontentloaded"
        )
        assert edited_title in page.content(), (
            f"edited title {edited_title!r} not visible in listing"
        )
    finally:
        cleanup = authed_get(f"{base_url}/wip/events/{new_id}/delete")
        assert cleanup["status"] < 400


@pytest.mark.mutates_db
def test_wip_event_image_upload(
    page: Page,
    base_url: str,
    profile,
    login,
    authed_post,
    tiny_jpeg_data_url: str,
) -> None:
    """Upload a tiny image to an existing event's gallery.

    Drives ``EventsWipView._add_image`` (line 248 of
    `crud/cbvs/events.py`) — the cropper data-URL path. We pick the
    first event the journalist owns from the listing rather than
    creating one inline so this test stays orthogonal to the
    create/edit lifecycle test above (different failure modes)."""
    journalist = profile(_PRESS_MEDIA_COMMUNITY)
    login(journalist)

    page.goto(
        f"{base_url}/wip/events/", wait_until="domcontentloaded"
    )
    event_id = _first_event_id_from_listing(page)
    if event_id is None:
        pytest.skip(
            "wip/events/ : no event owned by this journalist — seed "
            "data drift or pool exhausted"
        )

    resp = authed_post(
        f"{base_url}/wip/events/{event_id}/images/",
        {
            "_action": "add-image",
            "image": tiny_jpeg_data_url,
            "image_filename": "e2e-event-image.jpg",
            "caption": "e2e test caption",
            "copyright": "e2e test",
        },
    )
    assert resp["status"] < 400, f"events images POST : {resp}"
    assert "/auth/login" not in resp["url"]
    assert "/not-authorized" not in resp["url"]


def _first_option_value(page: Page, select_name: str) -> str:
    """Return the first non-empty option value for the named select.

    `RichSelectField` renders an empty `<select>` and a wrapper
    `<div x-data="{ ..., options: [['v','l'], ['v','l'], ...], ... }">`
    that Choices.js populates after `domcontentloaded`. We can't
    rely on `select.options` (raced with init) so we extract the
    first ['v','l'] pair from the literal `x-data` attribute."""
    return page.evaluate(
        """(name) => {
            const sel = document.querySelector(`select[name="${name}"]`);
            if (!sel) return '';
            const wrapper = sel.closest('[x-data]');
            if (!wrapper) return '';
            const xdata = wrapper.getAttribute('x-data') || '';
            // Find the first ['<value>', '<label>'] pair in the
            // options literal. Skips empty placeholders.
            const rx = /\\[\\s*'([^']*)'\\s*,\\s*'[^']*'\\s*\\]/g;
            let m;
            while ((m = rx.exec(xdata)) !== null) {
                if (m[1] && m[1].trim() !== '') return m[1];
            }
            return '';
        }""",
        select_name,
    )


def _scrape_form_values(page: Page) -> dict[str, str]:
    """Pull every named <input>/<textarea>/<select> value off the
    rendered form into a flat dict.

    Used for the edit round-trip : the server expects all fields back
    or it nulls them via `populate_obj`. Skips empty names, file
    inputs, and submit buttons. For multiple <select>, takes the
    first selected value (or the first option if none selected).

    Note : RichSelectField and CountrySelectField populate their
    real <select> via Choices.js after `domcontentloaded`. To get
    their value reliably we read from the Alpine `value:` slot in
    the wrapper's x-data when the <select> itself is empty."""
    return page.evaluate(
        """() => {
            const out = {};
            const skip_types = new Set(['file', 'submit', 'button']);
            // <input> + <textarea>
            for (const el of document.querySelectorAll(
                'input[name], textarea[name]'
            )) {
                const name = el.getAttribute('name');
                if (!name) continue;
                if (skip_types.has(el.type)) continue;
                if (el.type === 'checkbox' || el.type === 'radio') {
                    if (el.checked) out[name] = el.value || 'on';
                    continue;
                }
                out[name] = el.value || '';
            }
            // <select>
            for (const sel of document.querySelectorAll('select[name]')) {
                const name = sel.getAttribute('name');
                if (!name) continue;
                if (sel.value && sel.value !== '') {
                    out[name] = sel.value;
                    continue;
                }
                // Fall back to the Alpine `value:` slot when Choices.js
                // hasn't populated the real <select> yet.
                const wrapper = sel.closest('[x-data]');
                if (wrapper) {
                    const xd = wrapper.getAttribute('x-data') || '';
                    const m = xd.match(/value:\\s*'([^']*)'/);
                    if (m) {
                        out[name] = m[1] === 'None' ? '' : m[1];
                        continue;
                    }
                }
                out[name] = '';
            }
            return out;
        }"""
    )


def _find_event_id(page: Page, base_url: str, title: str) -> str | None:
    """Return the id of the row whose <tr> text contains `title`.

    Kept as a string : Event ids are snowflake-style (19 digits)
    which `parseInt` would round past Number.MAX_SAFE_INTEGER (~16
    digits)."""
    page.goto(f"{base_url}/wip/events/", wait_until="domcontentloaded")
    return page.evaluate(
        """(needle) => {
            // Restrict to <tr> rows so we don't catch the page-level
            // wrapper div that also contains the needle text + every
            // event-id link in the table.
            for (const row of document.querySelectorAll('tr')) {
                const text = row.textContent || '';
                if (!text.includes(needle)) continue;
                for (const a of row.querySelectorAll('a[href]')) {
                    const m = (a.getAttribute('href') || '').match(
                        /\\/wip\\/events\\/(\\d+)(?:\\/|$)/
                    );
                    if (m) return m[1];
                }
            }
            return null;
        }""",
        title,
    )


def _first_event_id_from_listing(page: Page) -> str | None:
    """Return the (string) id of the first event in the listing."""
    return page.evaluate(
        """() => {
            for (const a of document.querySelectorAll('a[href]')) {
                const m = (a.getAttribute('href') || '').match(
                    /^\\/wip\\/events\\/(\\d+)\\/?$/
                );
                if (m) return m[1];
            }
            return null;
        }"""
    )
