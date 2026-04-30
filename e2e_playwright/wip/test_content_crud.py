# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""WIP content CRUD — articles, communiqués, sujets, commandes,
avis-enquête.

All five resource types extend ``BaseWipView`` (`crud/cbvs/_base.py`)
and share the same `post()` handler ; they differ only in the form
class, the URL slug, and the community that owns them.

Existing tests :
- ``test_wip_lifecycle.py`` covers publish/unpublish for articles,
  communiqués and events.
- ``test_wip_subpages.py`` smokes GET on detail pages.
- ``test_eventroom.py`` covers create/edit/delete for events.

This file extends create / edit / delete to articles + communiqués
+ sujets + commandes — same `BaseWipView.post()` plumbing, four
slightly different forms.

Pattern (identical for each resource) :

1. GET /wip/<resource>/new/ — pull required RichSelectField values
   (`sector`, `section`, `topic`, `genre`, `media_id`...) from the
   rendered form.
2. POST /wip/<resource>/ with `_action=save` + required fields +
   placeholder text → flash `Enregistré` confirms creation.
3. Find the new row's id in the listing.
4. GET /wip/<resource>/edit/<id>/ → scrape every input/textarea/
   select via `_scrape_form_values` (browsers re-submit the full
   form ; partial POSTs raise NOT NULL violations on `populate_obj`).
5. Re-POST with title changed, assert flash again.
6. GET /wip/<resource>/<id>/delete (cleanup, soft-delete).

The helper functions are duplicated from ``test_eventroom.py``
deliberately ; once stable they could be promoted to a shared
helper module.

Marked ``mutates_db``.
"""

from __future__ import annotations

import re
import time

import pytest
from playwright.sync_api import Page

# (slug, community, required-rich-selects)
# `slug` is the URL segment under /wip/. Most resources use the
# same string as their CBV class (`articles`, etc.) ; avis-enquête
# uses a hyphen instead of underscore (`route_base = "avis-enquete"`).
# `required` lists the names of RichSelect/SimpleRichSelect fields
# that the form's WTForms validators mark `InputRequired` ; we pull
# a real ontology value for each from the rendered new-form.
RESOURCES = [
    (
        "articles",
        "PRESS_MEDIA",
        ("genre", "section", "topic", "sector", "media_id"),
    ),
    (
        "communiques",
        "PRESS_RELATIONS",
        ("sector", "section", "topic", "genre"),
    ),
    (
        "sujets",
        "PRESS_MEDIA",
        ("genre", "section", "topic", "sector", "media_id"),
    ),
    (
        "commandes",
        "PRESS_MEDIA",
        ("genre", "section", "topic", "sector", "media_id"),
    ),
    (
        "avis-enquete",
        "PRESS_MEDIA",
        ("genre", "section", "topic", "sector", "media_id"),
    ),
]


@pytest.mark.mutates_db
@pytest.mark.parametrize(
    ("slug", "community", "required_selects"),
    RESOURCES,
    ids=[r[0] for r in RESOURCES],
)
def test_wip_content_create_edit_delete(
    page: Page,
    base_url: str,
    profile,
    login,
    authed_post,
    authed_get,
    slug: str,
    community: str,
    required_selects: tuple[str, ...],
) -> None:
    journalist = profile(community)
    login(journalist)

    page.goto(
        f"{base_url}/wip/{slug}/new/", wait_until="domcontentloaded"
    )
    # Build the create payload from every form field the new-form
    # renders (so all `validate_choice=True` SelectFields get a
    # legitimate value, not just the ones that are
    # `InputRequired`). Then override each required select with the
    # first valid option from its x-data, since RichSelectFields
    # render empty by default.
    create_payload = _scrape_form_values(page)
    for name in required_selects:
        v = _first_option_value(page, name)
        if not v:
            pytest.skip(
                f"{slug}/new : empty options for required select "
                f"{name!r}"
            )
        create_payload[name] = v
    title = f"e2e-{slug}-{int(time.time() * 1000) % 10**10}"
    # Date placeholders : the WIP forms render `DateTimeField` with
    # no `InputRequired()` validator while the DB columns are
    # `Mapped[datetime]` (NOT NULL) — a model/form mismatch
    # (filed in `bugs/qualifies/wip-content-form-date-mismatch.md`).
    # The browser sidesteps this by always letting the user fill in
    # the dates ; we have to do the same explicitly. Use the
    # WTForms `format="%Y-%m-%dT%H:%M"` from the form definitions.
    future_date = "2030-01-15T10:00"
    for date_name in (
        "date_parution_prevue",
        "date_publication_aip24",
        "date_limite_validite",
        "date_bouclage",
        "date_paiement",
        "date_debut_enquete",
        "date_fin_enquete",
    ):
        if date_name in create_payload or _form_has_field(page, date_name):
            create_payload[date_name] = future_date
    create_payload.update({
        "_action": "save",
        "titre": title,
        "chapo": f"Chapô e2e {slug}",
        "contenu": f"<p>Contenu e2e {slug}</p>",
    })
    create = page.evaluate(
        """async (args) => {
            const r = await fetch(args.url, {
                method: 'POST', credentials: 'same-origin',
                body: new URLSearchParams(args.data),
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
            });
            return {status: r.status, url: r.url, body: await r.text()};
        }""",
        {
            "url": f"{base_url}/wip/{slug}/",
            "data": create_payload,
        },
    )
    if create["status"] >= 500:
        m = re.search(
            r"<h1[^>]*>([A-Z][A-Za-z]+(?:Error|Exception)[^<]*)</h1>",
            create["body"],
        )
        exc = m.group(1).strip() if m else "(no exc)"
        m2 = re.search(
            r"NotNullViolation[^<]*null value in column "
            r"&#34;(\w+)&#34;",
            create["body"],
        )
        col = m2.group(1) if m2 else "(unknown)"
        pytest.fail(
            f"{slug} POST create : 500 — exc={exc!r} "
            f"null-column={col!r} payload-keys="
            f"{sorted(create_payload.keys())}"
        )
    assert create["status"] < 400, f"{slug} POST create : {create}"
    assert "/auth/login" not in create["url"]
    # Confirm the success flash via the `window.toasts` JS literal.
    # The layout renders `window.toasts` twice (public + private both
    # call `get_flashed_messages()`) — one consumes the flashes, the
    # other is empty. We just need one of them to contain the
    # success marker.
    toasts_blocks = re.findall(
        r"window\.toasts\s*=\s*(\[[^;]*?\])\s*;", create["body"]
    )
    success_in_toasts = any(
        "Enregistr" in tb for tb in toasts_blocks
    )
    if not success_in_toasts:
        # Form validation failed silently — pull WTForms field
        # errors out of the re-rendered template so the failure
        # message tells you which fields tripped.
        field_errors = page.evaluate(
            """(html) => {
                const div = document.createElement('div');
                div.innerHTML = html;
                const out = [];
                for (const el of div.querySelectorAll(
                    '.errors li, .form-errors li, '
                    + '[class*="error"] li'
                )) {
                    const t = (el.textContent || '').trim();
                    if (t) out.push(t);
                }
                return out.slice(0, 8);
            }""",
            create["body"],
        )
        pytest.fail(
            f"{slug} POST create : no `Enregistré` flash. "
            f"field errors: {field_errors} ; "
            f"payload-keys={sorted(create_payload.keys())}"
        )

    new_id = _find_resource_id(page, base_url, slug, title)
    assert new_id is not None, (
        f"created {slug} {title!r} not in listing"
    )

    try:
        # Edit : scrape full rendered form, change title, re-submit.
        page.goto(
            f"{base_url}/wip/{slug}/edit/{new_id}/",
            wait_until="domcontentloaded",
        )
        full_form = _scrape_form_values(page)
        assert len(full_form) > 5, (
            f"edit form scrape returned only {len(full_form)} keys "
            f"({sorted(full_form.keys())}) — page may have 404'd"
        )
        full_form["_action"] = "save"
        full_form["id"] = new_id
        edited_title = f"{title}-edited"
        full_form["titre"] = edited_title

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
            {"url": f"{base_url}/wip/{slug}/", "data": full_form},
        )
        assert edit["status"] < 400, (
            f"{slug} POST edit : {edit['status']} {edit['url']}"
        )
        assert "/auth/login" not in edit["url"]
        # `Enregistré` flash is JSON-escaped in `window.toasts`.
        assert "Enregistr" in edit["body"], (
            f"{slug} POST edit : no `Enregistré` flash — "
            "validation likely failed silently."
        )
        page.goto(
            f"{base_url}/wip/{slug}/", wait_until="domcontentloaded"
        )
        assert edited_title in page.content(), (
            f"edited title {edited_title!r} not visible in listing"
        )
    finally:
        cleanup = authed_get(
            f"{base_url}/wip/{slug}/{new_id}/delete"
        )
        assert cleanup["status"] < 400


# --- Helpers (duplicated from test_eventroom for now) -----------------


def _first_option_value(page: Page, select_name: str) -> str:
    """Return the first non-empty option value for the named select.

    Handles both `RichSelectField` (where Choices.js populates the
    real <select> after `domcontentloaded`, leaving `select.options`
    empty) and `SimpleRichSelectField` (which renders the options
    directly in the HTML)."""
    return page.evaluate(
        """(name) => {
            const sel = document.querySelector(`select[name="${name}"]`);
            if (!sel) return '';
            // Direct <option> path : works for SimpleRichSelectField
            // and any non-Choices.js select that has options inline.
            for (const o of sel.options) {
                if (o.value && o.value.trim() !== '') return o.value;
            }
            // Alpine x-data path : works for RichSelectField (Choices.js
            // hasn't populated yet at domcontentloaded).
            const wrapper = sel.closest('[x-data]');
            if (!wrapper) return '';
            const xdata = wrapper.getAttribute('x-data') || '';
            const rx = /\\[\\s*'([^']*)'\\s*,\\s*'[^']*'\\s*\\]/g;
            let m;
            while ((m = rx.exec(xdata)) !== null) {
                if (m[1] && m[1].trim() !== '') return m[1];
            }
            return '';
        }""",
        select_name,
    )


def _form_has_field(page: Page, name: str) -> bool:
    """True if the rendered page contains a form field named `name`."""
    return page.evaluate(
        """(name) => Boolean(document.querySelector(
            `[name="${name}"]`
        ))""",
        name,
    )


def _scrape_form_values(page: Page) -> dict[str, str]:
    """Pull every named form field's value off the rendered form.

    Skips file inputs and submit buttons. Handling per field type :

    - <input type=date|datetime-local|...> with empty value : OMIT
      from output. Sending `field=""` makes WTForms `DateTimeField`
      try to parse `""` and raise « Not a valid datetime value » ;
      omitting the key lets the field default to None (acceptable
      for optional dates).
    - <select> with current selection : send `select.value`.
    - <select> with empty selection : try the Alpine `value:` slot
      (Choices.js hasn't populated yet at `domcontentloaded`).
      If still empty, fall back to the FIRST `['v','l']` pair in
      the `options:` literal — the only sensible default for
      `validate_choice=True` RichSelectFields when the form is
      submitted untouched."""
    return page.evaluate(
        """() => {
            const out = {};
            const skip_types = new Set(['file', 'submit', 'button']);
            const empty_date_types = new Set([
                'date', 'datetime-local', 'time', 'month', 'week',
            ]);
            for (const el of document.querySelectorAll(
                'input[name], textarea[name]'
            )) {
                const name = el.getAttribute('name');
                if (!name || skip_types.has(el.type)) continue;
                if (el.type === 'checkbox' || el.type === 'radio') {
                    if (el.checked) out[name] = el.value || 'on';
                    continue;
                }
                if (empty_date_types.has(el.type) && !el.value) {
                    // Skip — sending '' makes WTForms 400.
                    continue;
                }
                out[name] = el.value || '';
            }
            for (const sel of document.querySelectorAll('select[name]')) {
                const name = sel.getAttribute('name');
                if (!name) continue;
                if (sel.value && sel.value !== '') {
                    out[name] = sel.value;
                    continue;
                }
                const wrapper = sel.closest('[x-data]');
                let resolved = '';
                if (wrapper) {
                    const xd = wrapper.getAttribute('x-data') || '';
                    const vm = xd.match(/value:\\s*'([^']*)'/);
                    if (vm && vm[1] !== 'None') {
                        resolved = vm[1];
                    } else {
                        // Fall back to first option in `options:` literal.
                        const om = xd.match(
                            /\\[\\s*'([^']+)'\\s*,\\s*'[^']*'\\s*\\]/
                        );
                        if (om) resolved = om[1];
                    }
                }
                out[name] = resolved;
            }
            return out;
        }"""
    )


def _find_resource_id(
    page: Page, base_url: str, slug: str, title: str
) -> str | None:
    """Find the row whose <tr> contains `title`, return its id (str).

    Uses the listing's `q=` query param (the WIP listings filter by
    `M.titre.ilike(%q%)`, so a unique-per-run title gives one match).
    Kept as a string : ids are 19-digit snowflakes which `parseInt`
    rounds past Number.MAX_SAFE_INTEGER."""
    import urllib.parse

    page.goto(
        f"{base_url}/wip/{slug}/?q={urllib.parse.quote(title)}",
        wait_until="domcontentloaded",
    )
    return page.evaluate(
        """(args) => {
            const rx = new RegExp(
                `\\/wip\\/${args.slug}\\/(\\\\d+)(?:\\/|$)`
            );
            for (const row of document.querySelectorAll('tr')) {
                if (!(row.textContent || '').includes(args.needle)) continue;
                for (const a of row.querySelectorAll('a[href]')) {
                    const m = (a.getAttribute('href') || '').match(rx);
                    if (m) return m[1];
                }
            }
            return null;
        }""",
        {"needle": title, "slug": slug},
    )
