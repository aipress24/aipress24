# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""The Business Walls the caller manages, through the API."""

from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask.testing import FlaskClient
from PIL import Image
from sqlalchemy.orm import Session
from werkzeug.test import TestResponse

from app.enums import BWRoleType, BWStatus, RoleEnum
from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.api_v1.security import ALL_SCOPES, Scope
from app.modules.bw.bw_activation.models import SubscriptionStatus
from app.modules.bw.bw_activation.models.business_wall import BusinessWall
from app.modules.bw.bw_activation.user_utils import publishable_org_ids
from app.services.taxonomies import TaxonomyEntry

from .conftest import _email, _mint_token, _role

URL = "/api/v1/me/business-walls"
KIND = "leaders_experts"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _png() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (2, 2), "red").save(buffer, "PNG")
    return buffer.getvalue()


def _create(client: FlaskClient, token: str, **body) -> TestResponse:
    body = {"bw_type": KIND, "terms_accepted": True, **body}
    return client.post(URL, json=body, headers=_auth(token))


def _list(client: FlaskClient, token: str) -> list[dict]:
    return client.get(URL, headers=_auth(token)).get_json()["items"]


@pytest.fixture
def people(db_session: Session) -> SimpleNamespace:
    db_session.add_all(
        TaxonomyEntry(
            taxonomy_name="secteur_detaille",
            category=category,
            value=value,
            name=value,
            seq=1,
        )
        for category, value in [
            ("Industrie", "Industrie / Chimie"),
            ("Numérique", "Numérique / Cloud"),
        ]
    )
    organisation = Organisation(name="Abilian")
    admin = User(email=_email(), first_name="Ada", last_name="Min", active=True)
    admin.roles.append(_role(db_session, RoleEnum.ADMIN))
    admin.organisation = organisation
    member = User(email=_email(), first_name="Mem", last_name="Ber", active=True)
    member.organisation = organisation
    db_session.add_all([organisation, admin, member])
    db_session.commit()
    return SimpleNamespace(
        organisation=organisation,
        admin=admin,
        member=member,
        admin_token=_mint_token(db_session, admin, ALL_SCOPES),
        member_token=_mint_token(db_session, member, ALL_SCOPES),
        read_only=_mint_token(db_session, admin, [Scope.READ_SELF.value]),
    )


@pytest.fixture
def wall(client: FlaskClient, people: SimpleNamespace) -> dict:
    return _create(client, people.admin_token).get_json()


@pytest.mark.parametrize("bw_type", ["leaders_experts", "media"])
def test_an_administrator_opens_one_without_payment(
    client: FlaskClient, people: SimpleNamespace, db_session: Session, bw_type: str
) -> None:
    response = _create(client, people.admin_token, bw_type=bw_type)
    assert response.status_code == 201
    created = response.get_json()
    assert created["bw_type"] == bw_type
    assert created["name"] == "Abilian"
    assert created["missing"] == ["name", "siren"]
    page = created["_links"]["page"]["href"]
    assert page.startswith("/swork/organisations/x")

    db_session.expire_all()
    organisation = db_session.get(Organisation, people.organisation.id)
    assert organisation.bw_active == bw_type
    assert not organisation.is_auto
    # Those who were in the organisation still are.
    assert {u.id for u in organisation.members} == {people.admin.id, people.member.id}
    stored = db_session.get(BusinessWall, organisation.bw_id)
    assert stored.status == BWStatus.ACTIVE.value
    assert stored.subscription.status == SubscriptionStatus.ACTIVE.value
    assert stored.subscription.stripe_subscription_id is None
    (role,) = stored.role_assignments
    assert (role.user_id, role.role_type) == (people.admin.id, BWRoleType.BW_OWNER)
    assert db_session.get(User, people.admin.id).cgv_accepted_at
    assert organisation.id in publishable_org_ids(people.admin)


def test_only_an_administrator_opens_one(
    client: FlaskClient, people: SimpleNamespace, db_session: Session
) -> None:
    assert _create(client, people.member_token).status_code == 403
    assert _create(client, people.read_only).status_code == 403
    assert db_session.query(BusinessWall).count() == 0


@pytest.mark.parametrize(
    "body", [{"terms_accepted": False}, {"bw_type": "nope"}, {"owner_id": 1}]
)
def test_invalid_requests(
    client: FlaskClient, people: SimpleNamespace, db_session: Session, body: dict
) -> None:
    assert _create(client, people.admin_token, **body).status_code == 422
    assert db_session.query(BusinessWall).count() == 0


def test_an_organisation_has_one_at_most(
    client: FlaskClient, people: SimpleNamespace, wall: dict
) -> None:
    response = _create(client, people.admin_token)
    assert response.status_code == 409
    assert "already" in response.get_json()["message"]


def test_an_organisation_is_needed(
    client: FlaskClient, people: SimpleNamespace, db_session: Session
) -> None:
    people.admin.organisation = None
    db_session.commit()
    assert _create(client, people.admin_token).status_code == 409


def test_the_manager_edits_it(
    client: FlaskClient, people: SimpleNamespace, wall: dict, db_session: Session
) -> None:
    url = wall["_links"]["self"]["href"]
    answers = {
        "name": "Abilian SAS",
        "siren": "123456789",
        "presentation": "Éditeur de logiciels.",
        "secteurs_activite": ["Numérique"],
        "secteurs_activite_detail": ["Numérique / Cloud"],
        "site_url": "https://abilian.com/",
    }

    def patch(**query) -> dict:
        return client.patch(
            url,
            json={"answers": answers},
            query_string=query,
            headers=_auth(people.admin_token),
        ).get_json()

    assert set(patch(dry_run="true")["changed"]) == set(answers)
    assert _list(client, people.admin_token) == [wall]
    assert set(patch()["changed"]) == set(answers)
    assert patch()["changed"] == []
    (edited,) = _list(client, people.admin_token)
    assert edited["answers"] == {**wall["answers"], **answers}
    assert edited["missing"] == []
    assert edited == client.get(url, headers=_auth(people.admin_token)).get_json()
    db_session.expire_all()
    assert db_session.get(Organisation, people.organisation.id).bw_name == "Abilian SAS"


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("name", ""),
        ("siren", ""),
        ("site_url", "javascript:alert(1)"),
        ("presentation", "x" * 501),
        ("secteurs_activite", ["Pêche"]),
        ("secteurs_activite_detail", ["Numérique / Cloud"]),
        ("type_organisation", ["a", "b"]),
        ("status", "active"),
        ("owner_id", 1),
        ("payer_email", "x@example.com"),
        # Those of a press agency.
        ("agrement", "x"),
    ],
)
def test_answers_the_form_would_refuse(
    client: FlaskClient, people: SimpleNamespace, wall: dict, name: str, value: object
) -> None:
    response = client.patch(
        wall["_links"]["self"]["href"],
        json={"answers": {name: value}},
        headers=_auth(people.admin_token),
    )
    assert response.status_code == 422
    assert name in response.get_json()["errors"]
    assert _list(client, people.admin_token) == [wall]


def test_it_is_hidden_from_those_who_do_not_manage_it(
    client: FlaskClient, people: SimpleNamespace, wall: dict, db_session: Session
) -> None:
    stranger = User(email=_email(), first_name="O", last_name="Ther", active=True)
    stranger.roles.append(_role(db_session, RoleEnum.ADMIN))
    db_session.add(stranger)
    db_session.commit()
    stranger_token = _mint_token(db_session, stranger, ALL_SCOPES)
    url = wall["_links"]["self"]["href"]
    for token in (people.member_token, stranger_token):
        assert _list(client, token) == []
        assert client.get(url, headers=_auth(token)).status_code == 404
        response = client.patch(
            url, json={"answers": {"name": "x"}}, headers=_auth(token)
        )
        assert response.status_code == 404
    response = client.patch(
        url, json={"answers": {"name": "x"}}, headers=_auth(people.read_only)
    )
    assert response.status_code == 403


@pytest.mark.parametrize("picture", ["logo", "cover"])
def test_its_pictures_are_replaced(
    client: FlaskClient,
    people: SimpleNamespace,
    wall: dict,
    media_dir: Path,
    picture: str,
) -> None:
    def put(content: bytes, **form) -> TestResponse:
        return client.put(
            f"{wall['_links']['self']['href']}/{picture}",
            data={"image": (BytesIO(content), "logo.svg"), **form},
            headers=_auth(people.admin_token),
            content_type="multipart/form-data",
        )

    assert wall[f"{picture}_sha256"] is None
    response = put(_png(), copyright="© Abilian")
    assert response.status_code == 200
    updated = response.get_json()
    assert updated[f"{picture}_sha256"] == hashlib.sha256(_png()).hexdigest()
    assert updated["answers"][f"{picture}_image_copyright"] == "© Abilian"
    kept = put(_png()).get_json()
    assert kept["answers"][f"{picture}_image_copyright"] == "© Abilian"
    assert put(b"<svg/>").status_code == 422
