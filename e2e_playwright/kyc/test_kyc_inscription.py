# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""The KYC tunnel, end to end: an anonymous visitor becomes a member.

`test_kyc_smoke.py` checks that the routes answer and
`test_kyc_widgets.py` that the widgets are populated. Neither walks the
journey, and the wizard is where the parts meet: five tabs gated by a
client-side `pre_validate()`, two image croppers, a dozen required
fields per tab, a town list fetched over AJAX, then a server-side
WTForms pass that can reject everything the browser just accepted.

What these drive, none of which the other files reach:

- picking a community profile and landing on its questionnaire;
- the cropper — attach a JPEG, confirm it, and the base64 lands in the
  hidden field the server reads;
- the dual selects, where the second box only unlocks once the first
  has a value, and the town box only after `/kyc/towns/<code>` answers;
- the POST validating server-side rather than re-rendering the wizard —
  the two disagree easily, and only the POST creates a user;
- `/kyc/validation` then `/kyc/done`, which is what makes the account;
- the refusals: no terms accepted, or an address already taken.

The happy paths create accounts for real, hence `mutates_db`. A full
run leaves one inactive member per profile plus one for the sign-in
test, each addressed `e2e-kyc-<hex>@agencetca.info`. The two refusal
tests create nothing — that is what they assert.

Run them against a dev server::

    pytest e2e_playwright/kyc/test_kyc_inscription.py \
        --browser chromium --base-url=http://127.0.0.1:5001 -m ""
"""

from __future__ import annotations

import io
import re
import uuid
from typing import TYPE_CHECKING, NamedTuple

import pytest
from PIL import Image
from playwright.sync_api import Page, expect

if TYPE_CHECKING:
    from pathlib import Path

#: One profile per community family. Their questionnaires differ in
#: shape — P010 has twice the required fields on the organisation tab —
#: so a field type that only one of them uses is still exercised.
PROFILES = {
    "journaliste": "P002",
    "communicant": "P010",
    "expert": "P015",
}

#: `check_mail` runs the address through `validate_email`, which checks
#: for an MX record, so a reserved domain like `example.com` is refused.
#: This is the domain the CSV test accounts already use.
EMAIL_DOMAIN = "agencetca.info"

FIRST_NAME = "Testeur"
LAST_NAME = "E2E"

#: The checkbox that gates account creation, on the last tab.
TERMS_FIELD = "validation_gcu"

#: Fills every control of one tab that is not handled outside: images go
#: through the cropper, the addresses are typed for real. Rich selects
#: are set through the tom-select instance rather than by clicking — the
#: click path is `test_kyc_widgets.py`'s job, this file is about the
#: journey. `_detail` boxes wait for a second pass: they stay locked
#: until their parent has a value.
FILL_TAB = """
([index, secret, firstName, lastName, detailPass, skip]) => {
  const tab = document.querySelectorAll('.tab')[index];
  for (const el of tab.querySelectorAll('input, textarea, select')) {
    if (!el.name || el.name === 'csrf_token' || skip.includes(el.name)) continue;
    const isDetail = el.name.endsWith('_detail');
    if (el.tagName === 'SELECT') {
      if (isDetail !== detailPass) continue;
      const ts = el.tomselect;
      if (!ts || ts.items.length) continue;
      const values = Object.keys(ts.options).filter((v) => v !== '');
      if (!values.length) continue;
      ts.addItem(values[0], true);
      el.dispatchEvent(new Event('change', {bubbles: true}));
      continue;
    }
    if (detailPass || el.type === 'file' || el.type === 'hidden') continue;
    if (el.type === 'email') continue;
    if (el.tagName === 'TEXTAREA') el.value = 'Texte de recette e2e.';
    else switch (el.type) {
      case 'checkbox': el.checked = true; break;
      case 'password': el.value = secret; break;
      case 'tel': el.value = '0612345678'; break;
      case 'url': el.value = 'https://example.com'; break;
      case 'number': el.value = '1'; break;
      default:
        el.value = el.name === 'first_name' ? firstName
                 : el.name === 'last_name' ? lastName : 'Test';
    }
    el.dispatchEvent(new Event('input', {bubbles: true}));
    el.dispatchEvent(new Event('change', {bubbles: true}));
  }
}
"""

#: The fields the wizard is refusing, so a failure names them.
BLOCKING_FIELDS = """
(index) => [...document.querySelectorAll('.tab')[index]
    .querySelectorAll('input, select, textarea')]
  .filter((e) => e.classList.contains('invalid') || e.classList.contains('xinvalid')
                 || (e.hasAttribute('required') && !e.value))
  .map((e) => `${e.name || e.id}[${e.tagName.toLowerCase()}/${e.type}]`)
"""

TOWNS_LOADED = """
() => {
  const s = document.querySelector('select[name="pays_zip_ville_detail"]');
  return !!(s && s.tomselect && Object.keys(s.tomselect.options).length);
}
"""

COUNTRY_CHOSEN = """
() => {
  const s = document.querySelector('select[name="pays_zip_ville"]');
  return !!(s && s.tomselect && s.tomselect.items.length);
}
"""


class Identity(NamedTuple):
    """The addresses and secret one run signs up with."""

    address: str
    backup: str
    secret: str


def _new_identity() -> Identity:
    tag = uuid.uuid4().hex[:10]
    return Identity(
        address=f"e2e-kyc-{tag}@{EMAIL_DOMAIN}",
        backup=f"e2e-kyc-{tag}-bis@{EMAIL_DOMAIN}",
        # Unique per run, so nothing here doubles as a reusable credential.
        secret=f"Test-e2e-{tag}!A1",
    )


@pytest.fixture
def portrait(tmp_path: Path) -> Path:
    """A JPEG big enough for cropper.js to have something to crop.

    The session-wide `tiny_jpeg_bytes` is 4×4, which the cropper cannot
    work with.
    """
    path = tmp_path / "portrait.jpg"
    buffer = io.BytesIO()
    Image.new("RGB", (600, 600), (120, 120, 200)).save(buffer, format="JPEG")
    path.write_bytes(buffer.getvalue())
    return path


def _address_is_free(page: Page, base_url: str, address: str) -> bool:
    """Whether the app would still accept this address for a new member.

    `/kyc/check_mail/` answers `ok` while the address is unused. It is
    the app's own answer to "does this account exist", which keeps the
    check on the same side of the wire as the rest of the test.
    """
    response = page.request.get(f"{base_url}/kyc/check_mail/{address}")
    return response.text().strip() == "ok"


def _open_questionnaire(page: Page, base_url: str, profile_id: str) -> None:
    """Pick the community profile, the way the landing page offers it."""
    page.goto(f"{base_url}/kyc/profile", wait_until="domcontentloaded")
    page.check(f'input[type=radio][name=profile][value="{profile_id}"]')
    page.click('input[value="Suivant"], button:has-text("Suivant")')
    page.wait_for_load_state("domcontentloaded")

    assert f"/kyc/wizard/{profile_id}" in page.url, (
        f"picking {profile_id} landed on {page.url}, not on its questionnaire"
    )
    # Generous on purpose: this waits for tom-select to mount 23 rich
    # selects, not for it to be quick. A loaded machine exceeded 20 s.
    expect(page.locator(".ts-wrapper").first).to_be_attached(timeout=45_000)


def _upload_portraits(page: Page, portrait: Path) -> None:
    """Attach a photo to every image field and confirm the crop.

    Attaching a file opens cropper.js; the base64 only reaches the
    hidden field the server reads once «Valider l'image» is clicked.
    """
    inputs = page.locator('.tab input[type="file"]')
    count = inputs.count()
    if count == 0:
        return

    for index in range(count):
        inputs.nth(index).set_input_files(str(portrait))
        page.get_by_role("button", name="Valider l'image").first.click()

    # Only the cropper writes a data URL. A `*_preload_name` sibling
    # carries an already-stored image and would otherwise be counted.
    cropped = page.evaluate("""() => [...document.querySelectorAll('input[type=hidden]')]
        .filter((e) => e.name && e.value.startsWith('data:image'))
        .map((e) => e.name)""")
    assert len(cropped) == count, (
        f"{count} image(s) attached and cropped, but {cropped} carry a data "
        f"URL — the cropper did not hand its result to the form"
    )


def _type_addresses(page: Page, identity: Identity) -> None:
    """Type both addresses and let the availability check settle.

    The widget asks `/kyc/check_mail/<address>` and marks the field
    `xinvalid` until that answers `ok`, so the value cannot simply be
    assigned.
    """
    for name, value in (
        ("email", identity.address),
        ("email_secours", identity.backup),
    ):
        page.fill(f'input[name="{name}"]', value)
        page.locator(f'input[name="{name}"]').blur()

    page.wait_for_function(
        """() => [...document.querySelectorAll(
               'input[name=email], input[name=email_secours]')]
             .every((e) => e.value && !e.classList.contains('xinvalid'))""",
        timeout=20_000,
    )


def _complete_tab(page: Page, index: int, identity: Identity, skip: list[str]) -> None:
    """Fill one tab and check the wizard agrees to leave it."""
    args = [index, identity.secret, FIRST_NAME, LAST_NAME]
    page.evaluate("(i) => { currentTab = i; showTab(i); }", index)
    page.evaluate(FILL_TAB, [*args, False, skip])

    if page.evaluate(COUNTRY_CHOSEN):
        # `/kyc/towns/<code>` is 3.2 MB for France; the box stays empty
        # and locked until it lands.
        page.wait_for_function(TOWNS_LOADED, timeout=60_000)
    page.evaluate(FILL_TAB, [*args, True, skip])

    assert page.evaluate("() => pre_validate()"), (
        f"tab {index} refuses to validate; blocking fields: "
        f"{page.evaluate(BLOCKING_FIELDS, index)}"
    )


def _fill_and_submit(
    page: Page,
    base_url: str,
    portrait: Path,
    profile_id: str,
    identity: Identity,
    *,
    accept_terms: bool = True,
) -> None:
    """Walk the whole questionnaire and post it.

    Leaves the browser wherever the POST landed, so a caller can assert
    on both the accepted and the refused outcome.
    """
    page.set_default_timeout(30_000)
    _open_questionnaire(page, base_url, profile_id)
    _upload_portraits(page, portrait)
    _type_addresses(page, identity)

    skip = [] if accept_terms else [TERMS_FIELD]
    tabs = page.evaluate("() => document.querySelectorAll('.tab').length")
    assert tabs > 1, f"the questionnaire has {tabs} tab(s); expected several"
    for index in range(tabs):
        _complete_tab(page, index, identity, skip)

    # Leaving the last tab submits the form. The navigation has to be
    # awaited explicitly: `wait_for_load_state` is already satisfied by
    # the page being left, so it returns before the POST has landed.
    with page.expect_navigation(wait_until="domcontentloaded", timeout=60_000):
        page.evaluate(
            "() => { currentTab = document.querySelectorAll('.tab').length - 1;"
            " nextPrev(1); }"
        )


@pytest.mark.mutates_db
@pytest.mark.parametrize("profile_id", PROFILES.values(), ids=PROFILES.keys())
def test_a_visitor_can_complete_the_kyc_tunnel(
    page: Page, base_url: str, portrait: Path, profile_id: str
) -> None:
    """The whole inscription, from the profile picker to the account."""
    identity = _new_identity()
    assert _address_is_free(page, base_url, identity.address), (
        f"{identity.address} is already taken before the test starts"
    )

    _fill_and_submit(page, base_url, portrait, profile_id, identity)

    assert page.url.endswith("/kyc/validation"), (
        f"the questionnaire was refused server-side: landed on {page.url}. "
        f"`pre_validate()` passed every tab, so the browser and WTForms "
        f"disagree — see `_log_invalid_form` in the server output."
    )
    summary = page.content()
    assert identity.address in summary, (
        "the summary page does not show the address that was entered"
    )
    assert FIRST_NAME in summary, "the summary omits the first name entered"
    assert LAST_NAME in summary, "the summary omits the last name entered"

    page.goto(f"{base_url}/kyc/done", wait_until="domcontentloaded")

    assert page.url.endswith("/kyc/done"), (
        f"/kyc/done bounced to {page.url}: the questionnaire never reached "
        f"the session, so no account was created"
    )
    assert not _address_is_free(page, base_url, identity.address), (
        f"{identity.address} is still free after /kyc/done — no account created"
    )


def _sign_in(page: Page, base_url: str, address: str, secret: str) -> None:
    page.goto(f"{base_url}/auth/logout", wait_until="domcontentloaded")
    page.goto(f"{base_url}/auth/login", wait_until="domcontentloaded")
    page.fill('input[name="email"]', address)
    page.fill('input[name="password"]', secret)
    page.click('button[type="submit"], input[type="submit"]')
    page.wait_for_load_state("domcontentloaded")


@pytest.mark.mutates_db
def test_a_new_member_cannot_sign_in_before_validation(
    page: Page, base_url: str, portrait: Path, profiles: list[dict]
) -> None:
    """Signing up is not being admitted: the account waits on a human.

    `_make_new_kyc_user_record` leaves `active` false, so Flask-Security
    refuses the login. This also pins that `ACCEPT_ANY_PASSWORD`, which
    the e2e runs need, does not let an inactive account through — the
    flag replaces the password check, not the account check.

    An existing member signs in first. Without that, a broken selector
    or a renamed field would leave every login on `/auth/login` and the
    test would pass having proved nothing.
    """
    # The tunnel runs anonymously: signed in, `export_kyc_data` would
    # update that member instead of creating one.
    identity = _new_identity()
    _fill_and_submit(page, base_url, portrait, PROFILES["journaliste"], identity)
    page.goto(f"{base_url}/kyc/done", wait_until="domcontentloaded")
    assert not _address_is_free(page, base_url, identity.address), (
        "the account was not created, so the sign-in check would prove nothing"
    )

    known = profiles[0]
    _sign_in(page, base_url, known["email"], known["password"])
    assert "/auth/login" not in page.url, (
        f"{known['email']} cannot sign in either, so this test cannot tell a "
        f"refused account from a broken sign-in form"
    )

    _sign_in(page, base_url, identity.address, identity.secret)

    assert "/auth/login" in page.url, (
        f"a member awaiting validation reached {page.url} — an account that "
        f"nobody has approved must not be able to sign in"
    )


@pytest.mark.mutates_db
def test_refusing_the_terms_creates_no_account(
    page: Page, base_url: str, portrait: Path
) -> None:
    """Everything filled but the terms left unticked: no member.

    `done_page` reads `validation_gcu` out of the session and sends the
    visitor to `/kyc/undone` instead of creating the account. Marked
    `mutates_db` because it walks the same write path — it just must
    not reach the end of it.
    """
    identity = _new_identity()

    _fill_and_submit(
        page, base_url, portrait, PROFILES["journaliste"], identity, accept_terms=False
    )
    page.goto(f"{base_url}/kyc/done", wait_until="domcontentloaded")

    assert page.url.endswith("/kyc/undone"), (
        f"/kyc/done went to {page.url} without the terms being accepted"
    )
    assert _address_is_free(page, base_url, identity.address), (
        f"{identity.address} was registered even though the terms were refused"
    )


def test_an_address_already_in_use_is_refused(
    page: Page, base_url: str, profiles: list[dict]
) -> None:
    """The questionnaire will not start on someone else's address.

    `check_mail` answers empty for a known address and the widget keeps
    the field invalid, so the visitor never gets past the first tab.
    Read-only: nothing is ever submitted.
    """
    taken = profiles[0]["email"]
    assert not _address_is_free(page, base_url, taken), (
        f"{taken} is not registered on this target; the test needs an address "
        f"that is, to have anything to refuse"
    )

    _open_questionnaire(page, base_url, PROFILES["journaliste"])
    page.fill('input[name="email"]', taken)
    page.locator('input[name="email"]').blur()

    expect(page.locator('input[name="email"]')).to_have_class(
        re.compile(r"\bxinvalid\b"), timeout=20_000
    )
    assert not page.evaluate("() => { currentTab = 0; return pre_validate(); }"), (
        "the wizard let the first tab through with an address that is taken"
    )
