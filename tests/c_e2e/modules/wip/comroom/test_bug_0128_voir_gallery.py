# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Bug 0128: the "Voir" page (`/wip/communiques/<id>/`) of a communiqué must
render an `<img src=...>` for each attached ComImage — not just the form
fields. The PO replayed the scenario after the first fix landed and reported
that only the text was rendered, not "le carrousel d'images (avec légende
et ©)". The corrected fix wraps the Communique in `CommuniqueVM` and renders
the same Alpine-driven `carousel(...)` component used on the NEWS press
release page.

This is the integration-level proof: full request/response cycle through
`@templated(VIEW_TEMPLATE)` → `_view_ctx` → `extra_view_html` → carousel
template, with a real DB-backed Communique that owns ComImage rows.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.flask.routing import url_for
from app.lib.file_object_utils import create_file_object
from app.models.lifecycle import PublicationStatus
from app.modules.wip.models.comroom.communique import ComImage, Communique

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session

    from app.models.auth import User
    from app.models.organisation import Organisation


@pytest.fixture
def communique_with_title(
    db_session: Session, test_org: Organisation, test_user: User
) -> Communique:
    communique = Communique(owner=test_user, publisher=test_org)
    communique.titre = "Test Communique With Images"
    communique.contenu = "Content for image tests"
    communique.status = PublicationStatus.DRAFT
    db_session.add(communique)
    db_session.flush()
    return communique


def _attach_image(
    db_session: Session,
    communique: Communique,
    *,
    caption: str,
    position: int,
) -> ComImage:
    file_obj = create_file_object(
        content=b"fake-png-bytes",
        original_filename=f"img-{position}.png",
        content_type="image/png",
    )
    image = ComImage(
        communique_id=communique.id,
        owner=communique.owner,
        content=file_obj,
        caption=caption,
        copyright="© Test",
        position=position,
    )
    db_session.add(image)
    db_session.commit()
    return image


def test_view_renders_attached_images(
    logged_in_client: FlaskClient,
    communique_with_title: Communique,
    db_session: Session,
):
    _attach_image(
        db_session, communique_with_title, caption="Première image", position=0
    )
    _attach_image(
        db_session, communique_with_title, caption="Seconde image", position=1
    )

    url = url_for("CommuniquesWipView:get", id=communique_with_title.id)
    response = logged_in_client.get(url)
    assert response.status_code == 200

    html = response.data.decode()
    assert "Images" in html, "gallery section title missing from view"
    assert "Première image" in html
    assert "Seconde image" in html
    assert html.count("<img") >= 2, (
        f"expected >=2 <img> tags in the gallery, got {html.count('<img')}"
    )
