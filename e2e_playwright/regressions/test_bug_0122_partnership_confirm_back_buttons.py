# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Regression for bug #0122 — confirm-partnership page had no
explicit way back to the platform / BW management. The user
landed on « Partenariat accepté ! » and was stuck.

Fix : two CTAs (« Gérer mes Business Walls » + « Retour à la
plateforme ») inline in the success / refused card, in addition
to the discreet platform-return strip the BW layout already
includes top + bottom.

This regression :
- Walks the partnership setup like CM-2 (journalist invites
  agency → agency accepts).
- After the agency POSTs `accept`, the post-confirmation
  template renders. We probe for both CTA `data-testid`
  markers to pin them in place against future template
  refactors.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page

_ERICK_NAMED_BW_ID = "3be67123-b68d-48ad-9043-e2a206d18893"
_PR_BW_OWNER_EMAIL = "eliane+BrigitteWasser@agencetca.info"
# Brigitte's organisation's `bw_id`-resolved active BW (cf.
# CM-2). Pinning it ensures the partnership lands on the BW that
# `get_active_business_wall_for_organisation` returns for her,
# so she can accept it as the partner_bw owner.
_BRIGITTE_AGENCY_BW_ID = "662e153a-ab3b-4c52-994e-5b539f254589"

_CONFIRM_PARTNERSHIP_URL_RE = re.compile(
    r"http[s]?://[^/\s]+(/BW/confirm-partnership-invitation/"
    r"[a-f0-9-]+/[a-f0-9-]+)"
)


@pytest.mark.mutates_db
@pytest.mark.parallel_unsafe
def test_partnership_accepted_page_has_back_ctas(
    page: Page,
    base_url: str,
    profile,
    profiles,
    login,
    authed_post,
    mail_outbox,
) -> None:
    """End-to-end : trigger a partnership invite, accept it, then
    verify the confirmation page exposes the two CTAs (« Gérer
    mes Business Walls » + « Retour à la plateforme »).

    Mirrors CM-2 setup ; the only assertion difference is on the
    final page rather than on the publication chain."""
    journalist = profile("PRESS_MEDIA")
    pr_owner = next(
        (p for p in profiles if p["email"] == _PR_BW_OWNER_EMAIL),
        None,
    )
    if pr_owner is None:
        pytest.skip(f"{_PR_BW_OWNER_EMAIL} not in CSV")

    # ── step 1 : journalist invites agency to partnership
    login(journalist)
    sel = authed_post(
        f"{base_url}/BW/select-bw/{_ERICK_NAMED_BW_ID}", {}
    )
    assert sel["status"] < 400 and "/auth/login" not in sel["url"]
    page.goto(
        f"{base_url}/BW/manage-external-partners",
        wait_until="domcontentloaded",
    )
    options = page.locator(
        'select[name="pr_provider"] option[value]'
    ).evaluate_all(
        "els => els.map(e => e.value).filter(v => v && v !== '')"
    )
    if not options:
        pytest.skip("no PR-BW available for partnership")
    partner_bw_id = (
        _BRIGITTE_AGENCY_BW_ID
        if _BRIGITTE_AGENCY_BW_ID in options
        else options[0]
    )

    mail_outbox.reset()
    invite = authed_post(
        f"{base_url}/BW/manage-external-partners",
        {"pr_provider": partner_bw_id},
    )
    assert invite["status"] < 400 and "/auth/login" not in invite["url"]
    captured = mail_outbox.messages()
    if not captured:
        pytest.skip("partnership invitation mail not captured")
    confirm_path = next(
        (
            m.group(1)
            for body in (msg["body"] for msg in captured)
            if (m := _CONFIRM_PARTNERSHIP_URL_RE.search(body))
        ),
        None,
    )
    if confirm_path is None:
        pytest.skip("no confirmation URL in invitation mail body")

    # ── step 2 : agency owner accepts partnership
    login(pr_owner)
    try:
        accept = authed_post(
            f"{base_url}{confirm_path}", {"action": "accept"}
        )
        assert accept["status"] < 400, accept

        # ── step 3 : land on the post-action page and verify
        # both CTAs are present.
        # The accept POST returns an HX-Redirect (or follows the
        # redirect to the same `confirm-partnership-invitation`
        # URL with action=active). The fully-followed final URL
        # is what the user sees.
        page.goto(
            f"{base_url}{confirm_path}",
            wait_until="domcontentloaded",
        )
        body = page.content()
        assert "Partenariat accepté" in body or "déjà été traitée" in body, (
            f"unexpected post-accept page content : "
            f"{body[:300]!r}"
        )
        # The two new CTAs.
        assert (
            page.locator('[data-testid="back-to-bw"]').count() >= 1
        ), (
            "missing « Gérer mes Business Walls » CTA on "
            "post-partnership-accept page — bug #0122 regression"
        )
        assert (
            page.locator(
                '[data-testid="back-to-platform-card"]'
            ).count() >= 1
        ), (
            "missing « Retour à la plateforme » CTA on "
            "post-partnership-accept page — bug #0122 regression"
        )
        # And the layout-level platform-return strip should also
        # be present (top + bottom).
        layout_buttons = page.locator(
            '[data-testid="back-to-platform"]'
        ).count()
        assert layout_buttons >= 1, (
            "BW layout's `_back_to_platform.html` strip missing "
            "— bugs #0109/#0111/#0114 regression"
        )
    finally:
        # Cleanup : journalist revokes partnership.
        login(journalist)
        authed_post(
            f"{base_url}/BW/select-bw/{_ERICK_NAMED_BW_ID}", {}
        )
        authed_post(
            f"{base_url}/BW/manage-external-partners",
            {"revoke_partner_bw_id": partner_bw_id},
        )
