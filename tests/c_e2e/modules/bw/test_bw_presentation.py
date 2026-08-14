# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""The Business Wall « Présentation » field, end to end.

Ticket #0280 (Erick, 2026-08-03) : « Dans le KYC, il y a un champ
"présentation" mais pas dans le BW. Il faudrait rajouter ce champ qui
apparaîtra dans "A propos". 500 caractères suffisent. »

The field is only worth anything if what the BW owner types on B01 comes
back out on the organisation's public page, so this walks both ends.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.lib.base62 import base62

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session

    from app.models.organisation import Organisation
    from app.modules.bw.bw_activation.models import BusinessWall

PRESENTATION = "Nous accompagnons les industriels de la filière batterie."


class TestBwPresentation:
    def test_presentation_is_saved_and_shown_on_the_org_page(
        self,
        db_session: Session,
        authenticated_owner_client: FlaskClient,
        test_business_wall: BusinessWall,
        test_org: Organisation,
    ) -> None:
        response = authenticated_owner_client.post(
            "/BW/configure-content",
            data={
                "name": "Fake-Space Security",
                "siren": "123456789",
                "presentation": PRESENTATION,
            },
        )
        assert response.status_code in (200, 302)

        db_session.refresh(test_business_wall)
        assert test_business_wall.presentation == PRESENTATION

        org_page = authenticated_owner_client.get(
            f"/swork/organisations/{base62.encode(test_org.id)}"
        )
        assert org_page.status_code == 200
        body = org_page.data.decode()
        assert "Présentation" in body
        assert PRESENTATION in body

    def test_presentation_input_caps_at_500_characters(
        self,
        authenticated_owner_client: FlaskClient,
        test_business_wall: BusinessWall,
    ) -> None:
        """« 500 caractères suffisent » — the cap lives on the input, so a
        change of widget must not silently drop it."""
        body = authenticated_owner_client.get("/BW/configure-content").data.decode()

        start = body.index('<textarea name="presentation"')
        assert 'maxlength="500"' in body[start : start + 500]
