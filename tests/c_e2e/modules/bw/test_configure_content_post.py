# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""POSTing the stage-B1 content form writes what was submitted.

`configure_content` was a single 354-line handler with no POST coverage
at all — only two GET tests asserting a 200. It has
since been split into a shell plus a handful of `_apply_*` functions,
and the multi-select fields in particular are the part a careless
refactor loses silently: a Werkzeug `MultiDict` answers `.get()` with
the *first* value, so anything reading the form as a plain dict comes
back with one string where a list was posted, or with nothing at all.

These tests assert the persisted row, not the status code.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.modules.bw.bw_activation.models import BusinessWall

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session

#: The two fields the form refuses to go without.
VALID_MINIMUM = {"name": "Le Quotidien", "siren": "123456789"}


def _post(client: FlaskClient, **extra):
    return client.post(
        "/BW/configure-content", data=VALID_MINIMUM | extra, follow_redirects=False
    )


def _reload(db_session: Session, bw_id) -> BusinessWall:
    """Re-read the row from the database, past the identity map."""
    db_session.expire_all()
    bw = db_session.get(BusinessWall, bw_id)
    assert bw is not None, f"BusinessWall {bw_id} disappeared"
    return bw


def test_the_mandatory_fields_are_written(
    authenticated_owner_client: FlaskClient,
    db_session: Session,
    test_business_wall: BusinessWall,
) -> None:
    bw_id = test_business_wall.id
    response = _post(authenticated_owner_client)

    assert response.status_code in (302, 303)
    bw = _reload(db_session, bw_id)
    assert bw.name == "Le Quotidien"
    assert bw.siren == "123456789"


def test_a_missing_name_writes_nothing(
    authenticated_owner_client: FlaskClient,
    db_session: Session,
    test_business_wall: BusinessWall,
) -> None:
    """The mandatory check short-circuits before any assignment."""
    bw_id = test_business_wall.id
    before = test_business_wall.siren

    response = authenticated_owner_client.post(
        "/BW/configure-content", data={"name": "", "siren": "999999999"}
    )

    assert response.status_code in (302, 303)
    assert _reload(db_session, bw_id).siren == before


def test_a_missing_siren_writes_nothing(
    authenticated_owner_client: FlaskClient,
    db_session: Session,
    test_business_wall: BusinessWall,
) -> None:
    """`siren` used to be checked two thirds down, after `name` had
    already been assigned and flushed. Nothing was committed on that
    path either — this pins that it stays so."""
    bw_id = test_business_wall.id
    before = test_business_wall.name

    response = authenticated_owner_client.post(
        "/BW/configure-content", data={"name": "Nouveau Nom", "siren": ""}
    )

    assert response.status_code in (302, 303)
    assert _reload(db_session, bw_id).name == before


def test_text_fields_are_written(
    authenticated_owner_client: FlaskClient,
    db_session: Session,
    test_business_wall: BusinessWall,
) -> None:
    bw_id = test_business_wall.id
    _post(
        authenticated_owner_client,
        tva="FR12345678901",
        site_url="https://example.test",
        tel_standard="0102030405",
    )

    bw = _reload(db_session, bw_id)
    assert bw.tva == "FR12345678901"
    assert bw.site_url == "https://example.test"
    assert bw.tel_standard == "0102030405"


def test_a_multi_select_keeps_every_value(
    authenticated_owner_client: FlaskClient,
    db_session: Session,
    test_business_wall: BusinessWall,
) -> None:
    """The regression a dict-shaped read of the form loses silently."""
    bw_id = test_business_wall.id
    _post(
        authenticated_owner_client,
        type_presse_et_media=["Presse quotidienne", "Presse magazine"],
    )

    bw = _reload(db_session, bw_id)
    assert bw.type_presse_et_media == ["Presse quotidienne", "Presse magazine"]


def test_a_dual_select_keeps_its_detail_companion(
    authenticated_owner_client: FlaskClient,
    db_session: Session,
    test_business_wall: BusinessWall,
) -> None:
    """The parent list and its `_detail` list are written together."""
    bw_id = test_business_wall.id
    _post(
        authenticated_owner_client,
        secteurs_activite=["Culture"],
        secteurs_activite_detail=["Culture / Musique", "Culture / Cinéma"],
    )

    bw = _reload(db_session, bw_id)
    assert bw.secteurs_activite == ["Culture"]
    assert bw.secteurs_activite_detail == ["Culture / Musique", "Culture / Cinéma"]


def test_type_organisation_wraps_its_single_value(
    authenticated_owner_client: FlaskClient,
    db_session: Session,
    test_business_wall: BusinessWall,
) -> None:
    """Its parent arrives as one value where the others arrive as lists."""
    bw_id = test_business_wall.id
    _post(
        authenticated_owner_client,
        type_organisation="Média",
        type_organisation_detail=["Média / Presse"],
    )

    bw = _reload(db_session, bw_id)
    assert bw.type_organisation == ["Média"]
    assert bw.type_organisation_detail == ["Média / Presse"]


def test_presentation_can_be_cleared(
    authenticated_owner_client: FlaskClient,
    db_session: Session,
    test_business_wall: BusinessWall,
) -> None:
    """The one text field an empty submission is allowed to blank.

    Every other field keeps its value when submitted empty; this one
    compares against the stored value instead, so a user really can
    delete their presentation text.
    """
    bw_id = test_business_wall.id
    _post(authenticated_owner_client, presentation="Un quotidien régional.")
    assert _reload(db_session, bw_id).presentation == "Un quotidien régional."

    _post(authenticated_owner_client, presentation="")
    assert _reload(db_session, bw_id).presentation == ""


def test_the_org_name_follows_the_bw_name(
    authenticated_owner_client: FlaskClient,
    db_session: Session,
    test_business_wall: BusinessWall,
) -> None:
    bw_id = test_business_wall.id
    _post(authenticated_owner_client, name="Nom Renommé")

    bw = _reload(db_session, bw_id)
    assert bw.name == "Nom Renommé"
    assert bw.get_organisation().bw_name == "Nom Renommé"


def test_a_named_payer_is_stored_and_then_cleared(
    authenticated_owner_client: FlaskClient,
    db_session: Session,
    test_business_wall: BusinessWall,
) -> None:
    """Switching back to "the owner pays" must blank the billing contact."""
    bw_id = test_business_wall.id
    _post(
        authenticated_owner_client,
        payer_is_owner="false",
        payer_first_name="Jean",
        payer_last_name="Payeur",
        payer_email="jean@example.test",
    )

    bw = _reload(db_session, bw_id)
    assert bw.payer_is_owner is False
    assert bw.payer_first_name == "Jean"
    assert bw.payer_email == "jean@example.test"

    _post(authenticated_owner_client, payer_is_owner="true")

    bw = _reload(db_session, bw_id)
    assert bw.payer_is_owner is True
    assert bw.payer_first_name == ""
    assert bw.payer_email == ""
