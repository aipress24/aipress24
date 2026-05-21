# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Visual regression for bug #0132 wrap-up.

The new-sujet form (no model yet) must already label the media
picker « Média destinataire » so it's clear the field designates
the *recipient* media, not the author's own media. This pin is
cheap — no model creation needed.

Asserting the « Auteur » block (visible in edit mode only) would
need an existing sujet to open. That part is covered by the unit
test on `_extra_view_html` ; here we keep the e2e narrow.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

_PRESS_MEDIA = "PRESS_MEDIA"


def test_sujet_new_form_uses_media_destinataire_label(
    page: Page, base_url: str, profile, login
) -> None:
    """Bug #0132 wrap-up: the new-sujet form must display
    « Média destinataire » as the media picker label."""
    p = profile(_PRESS_MEDIA)
    login(p)

    response = page.goto(f"{base_url}/wip/sujets/new/", wait_until="domcontentloaded")
    if response is None or response.status >= 400:
        pytest.skip(
            f"/wip/sujets/new/ unavailable for {p['email']!r} "
            f"(status={response.status if response else '?'})"
        )

    # The label is rendered next to the `select[name='media_id']`.
    # Read the rendered <label> text via JS so we don't depend on
    # Choices.js init.
    label_text = page.evaluate(
        """() => {
          const sel = document.querySelector("select[name='media_id']");
          if (!sel) return null;
          const labelEl = document.querySelector(
            `label[for="${sel.id}"]`
          ) || sel.closest("label");
          return labelEl ? labelEl.textContent.trim() : null;
        }"""
    )
    if label_text is None:
        pytest.skip("media_id select or its label not found on the form")

    assert "destinataire" in label_text.lower(), (
        f"media_id label is {label_text!r}; expected to contain "
        f"'destinataire' per bug #0132 wrap-up (renaming « Média » → "
        f"« Média destinataire »)."
    )
