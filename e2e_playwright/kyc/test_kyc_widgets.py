# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""The KYC rich widgets, driven in a real browser.

`test_kyc_smoke.py` checks that the wizard *routes* — no 5xx, a form, a
CSRF token. It cannot check that the fields work, and the Python suite
cannot either: the taxonomies never reach the HTML. `dynform` passes
`choices=get_choices(param)` to the widget, the widget template dumps
them into an Alpine `x-data` attribute, and tom-select turns that into
options at runtime. Server-side every `<select>` on the page is empty::

    curl /kyc/wizard/P002 | grep 'name="civilite"' -A2
    <select id="F008" name="civilite" required x-ref="select"></select>

So the whole ontology-to-user chain is only observable here. A broken
link in it — an ontology renamed, `get_choices` raising, the template
losing the attribute — leaves a wizard that still returns 200 with a
form and a CSRF token, which is exactly what the smoke suite asserts.

Every test fails rather than skips when its target is missing: a green
run that found no widget would be worse than no test at all
(`notes/lessons-learned.md`, «"Status 200" is not "rendered correctly"»).

Run against a dev server::

    pytest e2e_playwright/kyc/test_kyc_widgets.py \
        --browser chromium --base-url=http://127.0.0.1:5000
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

#: Journaliste avec carte de presse — the richest profile, and the one
#: whose first tab carries both a single and a multiple rich select.
PROFILE_ID = "P002"

#: Profiles used for the general "every rich select is populated" pass.
#: Three communities is enough to catch an ontology that only one
#: questionnaire references; the smoke suite already covers all five
#: for rendering.
SAMPLED_PROFILES = ["P002", "P010", "P015"]

#: `civilite` -> the `civilite` taxonomy, a short closed list.
SINGLE_SELECT = "civilite"
SINGLE_SELECT_EXPECTED = {"Madame", "Monsieur"}

#: `langues` -> the `langue` taxonomy, a long list.
MULTI_SELECT = "langues"
MULTI_SELECT_EXPECTED = "Français"

#: A `multidual_*` field: two bound selects where picking in the first
#: unlocks the second. Lives on the third tab.
DUAL_PARENT = "interet_pol_adm"
DUAL_DETAIL = "interet_pol_adm_detail"
DUAL_TAB = 2


def _goto_wizard(page: Page, base_url: str, profile_id: str = PROFILE_ID) -> None:
    page.goto(f"{base_url}/kyc/wizard/{profile_id}", wait_until="domcontentloaded")
    # tom-select initialises on DOMContentLoaded; the wrappers are the
    # signal that it has run. Generous: the wizard mounts 23 rich selects,
    # and this waits for initialisation, not for it to be quick — a loaded
    # machine took more than 20 s and failed the run.
    expect(page.locator(".ts-wrapper").first).to_be_attached(timeout=45_000)


def _show_tab(page: Page, index: int) -> None:
    """Reveal one tab of the wizard.

    `wizard.html` shows a single `.tab` at a time and `nextPrev(1)` only
    advances when `pre_validate()` passes, so reaching a later tab
    through the UI means filling every required field before it. These
    tests are about the widgets, not the tab flow — which
    `test_wizard_refuses_to_advance_on_an_empty_required_field` covers —
    so they call the page's own `showTab` directly.
    """
    page.evaluate(f"showTab({index})")


def _control(page, name: str):
    """The clickable box tom-select puts next to the real `<select>`."""
    return page.locator(f'select[name="{name}"] ~ .ts-wrapper .ts-control').first


def _wrapper_classes(page: Page, name: str) -> str:
    return page.eval_on_selector(
        f'select[name="{name}"] ~ .ts-wrapper', "e => e.className"
    )


def _open(page: Page, name: str) -> None:
    """Open one widget's dropdown, closing whichever one was open."""
    page.keyboard.press("Escape")
    control = _control(page, name)
    assert control.count() == 1, (
        f"no tom-select control for {name!r}: the questionnaire no longer "
        f"has this field, or tom-select did not initialise"
    )
    control.click()
    # Opening is not synchronous with the click on every engine: wait for
    # the widget to say it is open rather than for a frame to have passed.
    page.wait_for_function(
        """(name) => {
            const select = document.querySelector(`select[name="${name}"]`);
            return !!(select && select.tomselect && select.tomselect.isOpen);
        }""",
        arg=name,
        timeout=15_000,
    )


def _options_of(page: Page, name: str):
    """The clickable options of one widget's dropdown."""
    return page.locator(
        f'select[name="{name}"] ~ .ts-wrapper .ts-dropdown [data-value]'
    )


def _visible_options(page: Page, name: str) -> list[str]:
    """The labels one widget is offering, asked of that widget.

    Not `document.querySelector('.ts-dropdown:not([style*="display: none"])')`:
    the page holds 23 of them, and one that has never been opened carries
    no inline style at all, so it matches that `:not()` and answers for
    the wrong field. Which one came first differed between engines.
    """
    return page.evaluate(
        """(name) => {
            const select = document.querySelector(`select[name="${name}"]`);
            const ts = select && select.tomselect;
            if (!ts || !ts.isOpen) return [];
            return [...ts.dropdown_content.querySelectorAll('[data-value]')]
                .map((o) => o.textContent.trim());
        }""",
        name,
    )


def test_single_select_offers_its_taxonomy(page: Page, base_url: str) -> None:
    """A `list_*` field reaches the user with the taxonomy behind it."""
    _goto_wizard(page, base_url)
    _open(page, SINGLE_SELECT)

    options = set(_visible_options(page, SINGLE_SELECT))

    assert options >= SINGLE_SELECT_EXPECTED, (
        f"{SINGLE_SELECT!r} lists {sorted(options)} — expected at least "
        f"{sorted(SINGLE_SELECT_EXPECTED)}. The `civilite` taxonomy is not "
        f"reaching the widget."
    )


def test_multi_select_offers_its_taxonomy(page: Page, base_url: str) -> None:
    """A `multi_*` field is populated from a long taxonomy."""
    _goto_wizard(page, base_url)
    _open(page, MULTI_SELECT)

    options = _visible_options(page, MULTI_SELECT)

    assert MULTI_SELECT_EXPECTED in options, (
        f"{MULTI_SELECT!r} does not offer {MULTI_SELECT_EXPECTED!r} "
        f"(got {len(options)} options: {options[:5]})"
    )


def test_multi_select_accepts_several_values(page: Page, base_url: str) -> None:
    """`multiple` is not decoration: two picks must both reach the form.

    The `<select>` is what gets posted, so this is what `_parse_valid_form`
    will see — not what tom-select happens to draw.
    """
    _goto_wizard(page, base_url)
    _open(page, MULTI_SELECT)
    dropdown = _options_of(page, MULTI_SELECT)
    assert dropdown.count() >= 2, f"{MULTI_SELECT!r} offers fewer than 2 options"

    dropdown.nth(0).click()
    _open(page, MULTI_SELECT)
    dropdown.nth(1).click()

    selected = page.eval_on_selector(
        f'select[name="{MULTI_SELECT}"]',
        "e => [...e.selectedOptions].map(o => o.value)",
    )
    assert len(selected) == 2, (
        f"picked two languages, the posted <select> holds {selected}"
    )


def test_dual_select_detail_unlocks_when_the_parent_is_chosen(
    page: Page, base_url: str
) -> None:
    """`multidual_*`: the detail box stays locked until the first is set.

    This is the only field family with behaviour of its own rather than
    a plain list, and `DualSelectField` is the widget `dynform` builds
    for it.
    """
    _goto_wizard(page, base_url)
    _show_tab(page, DUAL_TAB)

    assert "disabled" in _wrapper_classes(page, DUAL_DETAIL), (
        f"{DUAL_DETAIL!r} is editable before {DUAL_PARENT!r} has a value"
    )

    _open(page, DUAL_PARENT)
    options = _options_of(page, DUAL_PARENT)
    assert options.count() > 0, f"{DUAL_PARENT!r} offers nothing to pick"
    options.first.click()
    page.keyboard.press("Escape")

    chosen = page.eval_on_selector(
        f'select[name="{DUAL_PARENT}"]', "e => [...e.selectedOptions].map(o => o.value)"
    )
    assert chosen, f"clicking an option left {DUAL_PARENT!r} empty"
    expect(
        page.locator(f'select[name="{DUAL_DETAIL}"] ~ .ts-wrapper')
    ).not_to_have_class(re.compile(r"\bdisabled\b"))


#: Fields whose taxonomy has no rows, so the widget renders empty.
#: Kept empty on purpose: a name here means real users see a field they
#: cannot fill, so it wants fixing rather than tolerating.
KNOWN_EMPTY_FIELDS: set[str] = set()


@pytest.mark.parametrize("profile_id", SAMPLED_PROFILES)
def test_every_rich_select_is_populated(
    page: Page, base_url: str, profile_id: str
) -> None:
    """No questionnaire ships a rich select with an empty option list.

    Catches the case a per-field test cannot: one ontology among dozens
    that resolves to nothing, on a profile nobody thought to check.
    tom-select moves the options into its own state, so the count comes
    from the instance and not from the `<select>`.
    """
    _goto_wizard(page, base_url, profile_id)

    # A `*_detail` box is the second half of a dual select and is filled
    # in from the first one, so it is empty until something is picked —
    # `test_dual_select_detail_unlocks_when_the_parent_is_chosen` covers
    # that pair.
    empty = page.evaluate("""() => {
        const out = [];
        for (const s of document.querySelectorAll('select[name]')) {
            if (!s.tomselect || s.name.endsWith('_detail')) continue;
            if (Object.keys(s.tomselect.options).length === 0) out.push(s.name);
        }
        return out;
    }""")
    total = page.evaluate(
        "() => [...document.querySelectorAll('select[name]')]"
        ".filter(s => s.tomselect && !s.name.endsWith('_detail')).length"
    )
    unexpected = sorted(set(empty) - KNOWN_EMPTY_FIELDS)

    assert total > 0, f"/kyc/wizard/{profile_id} rendered no rich select at all"
    assert not unexpected, (
        f"/kyc/wizard/{profile_id}: {len(unexpected)} of {total} rich selects "
        f"offer nothing to pick — {unexpected}. Their ontology resolves to no "
        f"rows, so the field is unusable."
    )


def test_mandatory_fields_carry_the_marker(page: Page, base_url: str) -> None:
    """A `kyc_code` of "M" and the `(*)` in the label are one decision.

    `dynform` writes both — the code into `render_kw`, the marker into
    the label — so a field flagged required in one place and not the
    other means the two paths have drifted.
    """
    _goto_wizard(page, base_url)

    mismatched = page.evaluate("""() => {
        const bad = [];
        for (const el of document.querySelectorAll('[kyc_code="M"]')) {
            const label = el.id ? document.querySelector(`label[for="${el.id}"]`) : null;
            if (!label || !label.textContent.includes('(*)')) {
                bad.push(el.getAttribute('name'));
            }
        }
        return bad;
    }""")
    total = page.locator('[kyc_code="M"]').count()

    assert total > 0, "no mandatory field on the first tab — nothing verified"
    assert not mismatched, (
        f"{len(mismatched)}/{total} mandatory fields are unmarked in their "
        f"label: {mismatched}"
    )


def test_wizard_refuses_to_advance_on_an_empty_required_field(
    page: Page, base_url: str
) -> None:
    """`pre_validate()` gates «Suivant»: an empty required tab stays put."""
    _goto_wizard(page, base_url)
    assert page.locator('[kyc_code="M"]').count() > 0, (
        "first tab has no required field — the gate cannot be exercised"
    )

    advanced = page.evaluate("() => { nextPrev(1); return currentTab; }")

    assert advanced == 0, (
        f"the wizard moved to tab {advanced} with required fields empty — "
        f"pre_validate() is not gating «Suivant»"
    )


#: The country/town pair: unlike `multidual_*`, the second box is not
#: embedded in the page — picking a country makes the widget fetch
#: `/kyc/towns/<code>`.
COUNTRY_FIELD = "pays_zip_ville"
COUNTRY_DETAIL = "pays_zip_ville_detail"
COUNTRY_TAB = 1


@pytest.mark.slow
def test_country_select_loads_its_towns_over_ajax(page: Page, base_url: str) -> None:
    """Choosing a country fills the town box from `/kyc/towns/<code>`.

    Marked slow on purpose: France alone is a 3.2 MB response and some
    37 000 options, so this takes a few seconds. That size is also why
    the assertion waits on the option count rather than a fixed delay.
    """
    _goto_wizard(page, base_url)
    _show_tab(page, COUNTRY_TAB)

    _open(page, COUNTRY_FIELD)
    options = _options_of(page, COUNTRY_FIELD)
    assert options.count() > 0, f"{COUNTRY_FIELD!r} lists no country"
    options.first.click()
    page.keyboard.press("Escape")

    page.wait_for_function(
        """() => {
            const s = document.querySelector('select[name="pays_zip_ville_detail"]');
            return s && s.tomselect && Object.keys(s.tomselect.options).length > 0;
        }""",
        timeout=30_000,
    )

    assert "disabled" not in _wrapper_classes(page, COUNTRY_DETAIL), (
        f"{COUNTRY_DETAIL!r} has towns but is still locked"
    )
