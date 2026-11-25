# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""The API asks the same questions as the form, for each type of Business Wall."""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup
from flask.testing import FlaskClient
from sqlalchemy.orm import Session

from app.modules.api_v1.business_walls import business_wall_fields
from app.modules.bw.bw_activation.config import BW_TYPES
from app.modules.bw.bw_activation.models import BusinessWall

# The API sends the pictures apart, and leaves the billing to the site.
LEFT_OUT = ("payer_", "logo_image", "bandeau_image", "csrf_token")


@pytest.mark.parametrize("bw_type", list(BW_TYPES))
def test_the_fields_are_those_of_the_form(
    authenticated_owner_client: FlaskClient,
    db_session: Session,
    test_business_wall: BusinessWall,
    bw_type: str,
) -> None:
    test_business_wall.bw_type = bw_type
    db_session.commit()
    page = authenticated_owner_client.get("/BW/configure-content")
    assert page.status_code == 200
    form = BeautifulSoup(page.data, "html.parser").select_one("form:has([name=siren])")
    asked = {tag["name"] for tag in form.select("[name]")}
    fields = business_wall_fields(bw_type)
    offered = {field.name for field in fields} - {"logo_image_copyright"}
    assert offered == {name for name in asked if not name.startswith(LEFT_OUT)}
    assert "logo_image_copyright" in asked
    limits = {
        tag["name"]: int(tag["maxlength"]) for tag in form.select("[maxlength][name]")
    }
    assert limits.items() <= {f.name: f.max_length for f in fields}.items()
