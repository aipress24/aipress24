# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""The professional profile through the API."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from flask.testing import FlaskClient
from sqlalchemy.orm import Session
from werkzeug.test import TestResponse

from app.enums import RoleEnum
from app.models.auth import KYCProfile, User
from app.models.organisation import Organisation
from app.modules.api_v1.profile import NOT_EDITABLE, profile_fields
from app.modules.api_v1.security import ALL_SCOPES, Scope
from app.modules.bw.bw_activation.models.business_wall import BusinessWall
from app.modules.kyc.populate_profile import populate_json_field
from app.modules.kyc.survey_model import get_survey_fields, get_survey_model
from app.services.taxonomies import TaxonomyEntry
from app.services.zip_codes import CountryEntry, ZipCodeEntry

from .conftest import _email, _mint_token, _role

URL = "/api/v1/me/profile"
LEADER = "P014"
STARTUP = "P018"
MEUDON = "FRA / 92190 Meudon"
JSON_FIELDS = (
    "show_contact_details",
    "info_personnelle",
    "info_professionnelle",
    "match_making",
    "info_hobby",
    "business_wall",
)
ANSWERS = {
    "metier_principal": ["Numérique"],
    "metier_principal_detail": ["Numérique / CTO"],
    "competences": ["Droit", "Retirée"],
    "langues": ["Français"],
    "formations": "ENS",
    "nom_orga": "Acme",
    "secteurs_activite_detailles": ["Industrie"],
    "pays_zip_ville": "FRA",
    "pays_zip_ville_detail": [MEUDON],
    "hobbies": "Échecs",
}


@pytest.fixture
def vocabularies(db_session: Session) -> None:
    db_session.add_all(
        TaxonomyEntry(
            taxonomy_name=name, category=category, value=value, name=value, seq=seq
        )
        for seq, (name, category, value) in enumerate(
            [
                ("metier", "Numérique", "Numérique / CTO"),
                ("metier", "Numérique", "Numérique / Développeur"),
                ("metier", "Santé", "Santé / Médecin"),
                ("competence_expert", "", "Droit"),
                ("langue", "", "Français"),
                ("langue", "", "Anglais"),
                ("secteur_detaille", "Industrie", "Industrie / Chimie"),
                ("civilite", "", "M"),
                ("civilite", "", "F"),
            ]
        )
    )
    db_session.add_all(
        [
            CountryEntry(iso3="FRA", name="France", seq=1),
            CountryEntry(iso3="BEL", name="Belgique", seq=2),
            ZipCodeEntry(
                iso3="FRA",
                zip_code="92190",
                name="Meudon",
                value=MEUDON,
                label="92190 Meudon",
            ),
        ]
    )
    db_session.commit()


@pytest.fixture
def member(db_session: Session, vocabularies: None) -> SimpleNamespace:
    user = User(
        email=_email(), first_name="Ada", last_name="Lovelace", gender="F", active=True
    )
    user.tel_mobile = "0601020304"
    user.roles.append(_role(db_session, RoleEnum.EXPERT))
    for name in ("PRESS_MEDIA", "PRESS_RELATIONS", "TRANSFORMER", "ACADEMIC"):
        _role(db_session, RoleEnum[name])
    user.profile = KYCProfile(
        profile_id=LEADER,
        profile_code="XP_DIR_ANY",
        profile_community="LEADERS_EXPERTS",
        presentation="Avant.",
        notification_preferences={},
        **{name: populate_json_field(name, ANSWERS) for name in JSON_FIELDS},
    )
    db_session.add(user)
    db_session.commit()
    return SimpleNamespace(
        user=user,
        token=_mint_token(db_session, user, ALL_SCOPES),
        read_only=_mint_token(db_session, user, [Scope.READ_SELF.value]),
    )


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _get(client: FlaskClient, member: SimpleNamespace) -> dict:
    response = client.get(URL, headers=_auth(member.token))
    assert response.status_code == 200
    return response.get_json()


def _patch(
    client: FlaskClient, member: SimpleNamespace, dry_run: bool = False, **body
) -> TestResponse:
    query = {"dry_run": "true"} if dry_run else None
    return client.patch(URL, json=body, query_string=query, headers=_auth(member.token))


def _clones(db_session: Session) -> list[User]:
    return list(db_session.scalars(sa.select(User).where(User.is_clone.is_(True))))


def test_the_profile_is_described(client: FlaskClient, member: SimpleNamespace) -> None:
    profile = _get(client, member)
    assert profile["type"] == LEADER
    assert not profile["awaiting_validation"]
    assert profile["answers"]["presentation"] == "Avant."
    assert profile["answers"]["metier_principal"] == ["Numérique"]
    assert profile["missing"] == []
    fields = {field["name"]: field for field in profile["fields"]}
    assert set(fields) == set(profile["answers"])
    assert not {"email", "password", "photo", "validation_gcu"} & set(fields)
    assert fields["metier_principal"]["moderated"]
    assert fields["metier_principal_detail"] == {
        "name": "metier_principal_detail",
        "label": "Détails (Métiers)",
        "section": "INFORMATIONS PERSONNELLES",
        "kind": "choices",
        "required": False,
        "moderated": False,
        "max_length": 0,
        "max_items": 0,
        "vocabulary": "metier",
        "parent": "metier_principal",
    }


def test_every_question_of_the_survey_is_handled() -> None:
    for survey in get_survey_model()["profiles"]:
        assert profile_fields(survey)
    handled = {
        field.name
        for survey in get_survey_model()["profiles"]
        for field in profile_fields(survey)
    }
    left_out = {f.name for f in get_survey_fields() if f.type in NOT_EDITABLE}
    assert {f.name for f in get_survey_fields()} <= handled | left_out


def test_answers_are_changed_and_the_others_kept(
    client: FlaskClient, member: SimpleNamespace, db_session: Session
) -> None:
    before = _get(client, member)["answers"]
    changes = {"presentation": " Après. ", "langues": ["Anglais", "Français"]}
    report = _patch(client, member, answers=changes).get_json()
    assert report["changed"] == ["presentation", "langues"]
    assert not report["awaiting_validation"]
    after = _get(client, member)
    assert after["answers"] == {
        **before,
        "presentation": "Après.",
        "langues": ["Anglais", "Français"],
    }
    db_session.expire_all()
    user = db_session.get(User, member.user.id)
    assert user.active
    assert user.tel_mobile == "0601020304"
    assert user.email == member.user.email
    assert _clones(db_session) == []


def test_naming_an_organisation_joins_it(
    client: FlaskClient, member: SimpleNamespace, db_session: Session
) -> None:
    organisation = Organisation(name="Abilian")
    db_session.add(organisation)
    db_session.commit()
    report = _patch(client, member, answers={"nom_orga": "Abilian"}).get_json()
    assert report["organisation_name"] == "Abilian"
    db_session.expire_all()
    user = db_session.get(User, member.user.id)
    assert user.organisation_id == organisation.id


def test_a_business_wall_keeps_its_members(
    client: FlaskClient, member: SimpleNamespace, db_session: Session
) -> None:
    organisation = Organisation(name="Acme")
    member.user.organisation = organisation
    db_session.add(organisation)
    db_session.flush()
    db_session.add(
        BusinessWall(
            bw_type="leaders_experts",
            status="active",
            owner_id=member.user.id,
            payer_id=member.user.id,
            organisation_id=organisation.id,
        )
    )
    db_session.commit()
    response = _patch(client, member, answers={"nom_orga": "Abilian"})
    assert response.status_code == 409
    assert _get(client, member)["answers"]["nom_orga"] == "Acme"
    accepted = _patch(client, member, answers={"hobbies": "Go"})
    assert accepted.status_code == 200


def test_the_main_answers_await_a_moderator(
    client: FlaskClient, member: SimpleNamespace, db_session: Session
) -> None:
    changes = {"metier_principal": ["Santé"], "metier_principal_detail": []}
    report = _patch(client, member, answers=changes).get_json()
    assert report["awaiting_validation"]
    profile = _get(client, member)
    assert profile["awaiting_validation"]
    assert profile["answers"]["metier_principal"] == ["Numérique"]
    (clone,) = _clones(db_session)
    assert clone.cloned_user_id == member.user.id
    # A second change would be lost when the first one is validated.
    assert _patch(client, member, answers={"hobbies": "Go"}).status_code == 409


@pytest.mark.parametrize(
    ("answers", "field"),
    [
        ({"nope": "x"}, "nope"),
        ({"email": "x@example.com"}, "email"),
        ({"formations": " "}, "formations"),
        ({"presentation": "x" * 301}, "presentation"),
        ({"presentation": ["x"]}, "presentation"),
        ({"langues": "Anglais"}, "langues"),
        ({"langues": ["Klingon"]}, "langues"),
        ({"macaron_repas": "yes"}, "macaron_repas"),
        ({"civilite": "X"}, "civilite"),
        ({"url_site_web": "javascript:alert(1)"}, "url_site_web"),
        ({"email_relation_presse": "nope"}, "email_relation_presse"),
        ({"metier": ["Numérique / CTO"]}, "metier"),
        ({"metier_detail": ["Numérique / CTO"]}, "metier_detail"),
        ({"metier_principal": ["Santé"]}, "metier_principal_detail"),
        ({"pays_zip_ville": "BEL"}, "pays_zip_ville_detail"),
        ({"pays_zip_ville_detail": ["FRA / 1 Nulle-Part"]}, "pays_zip_ville_detail"),
        ({"pays_zip_ville_detail": [MEUDON, "x"]}, "pays_zip_ville_detail"),
    ],
)
def test_answers_the_form_would_refuse(
    client: FlaskClient,
    member: SimpleNamespace,
    db_session: Session,
    answers: dict,
    field: str,
) -> None:
    before = _get(client, member)
    response = _patch(client, member, answers={"hobbies": "Go", **answers})
    assert response.status_code == 422
    assert field in response.get_json()["errors"]
    assert _get(client, member) == before
    assert _clones(db_session) == []


def test_a_refused_value_comes_with_the_closest_ones(
    client: FlaskClient, member: SimpleNamespace
) -> None:
    response = _patch(client, member, answers={"langues": ["anglai"]})
    (problem,) = response.get_json()["errors"]["langues"]
    assert problem == "'anglai' is not an accepted value (closest: Anglais)"


def test_a_value_dropped_since_is_kept(
    client: FlaskClient, member: SimpleNamespace
) -> None:
    response = _patch(client, member, answers={"competences": ["Retirée"]})
    assert response.status_code == 200
    assert _get(client, member)["answers"]["competences"] == ["Retirée"]


def test_nothing_is_changed_by_a_dry_run(
    client: FlaskClient, member: SimpleNamespace
) -> None:
    before = _get(client, member)
    changes = {"hobbies": "Go", "first_name": "Augusta"}
    report = _patch(client, member, dry_run=True, answers=changes).get_json()
    assert report["changed"] == ["first_name", "hobbies"]
    assert report["awaiting_validation"]
    assert _get(client, member) == before


def test_the_same_answers_change_nothing(
    client: FlaskClient, member: SimpleNamespace, db_session: Session
) -> None:
    before = _get(client, member)
    report = _patch(client, member, answers=before["answers"]).get_json()
    assert report["changed"] == []
    assert _clones(db_session) == []


def test_the_type_of_profile_changes(
    client: FlaskClient, member: SimpleNamespace
) -> None:
    report = _patch(client, member, type=STARTUP).get_json()
    assert report["type_changed"]
    profile = _get(client, member)
    assert profile["type"] == STARTUP
    assert profile["answers"]["hobbies"] == "Échecs"
    assert _patch(client, member, type="P999").status_code == 422
    # It asks for a transformation, which this member has not given.
    response = _patch(client, member, type="P021")
    assert "transformation_majeure" in response.get_json()["errors"]


def test_another_type_is_described(
    client: FlaskClient, member: SimpleNamespace
) -> None:
    def get(type_id: str) -> TestResponse:
        return client.get(
            URL, query_string={"type": type_id}, headers=_auth(member.token)
        )

    described = get("P021").get_json()
    assert described["type"] == "P021"
    assert described["missing"] == ["transformation_majeure"]
    assert described["answers"]["hobbies"] == "Échecs"
    assert get("P999").status_code == 422
    assert _get(client, member)["type"] == LEADER


def test_the_scope_is_required(client: FlaskClient, member: SimpleNamespace) -> None:
    response = client.patch(URL, json={"answers": {}}, headers=_auth(member.read_only))
    assert response.status_code == 403


def test_an_account_without_a_profile(
    client: FlaskClient, seed: SimpleNamespace
) -> None:
    assert client.get(URL, headers=_auth(seed.token)).status_code == 409


def test_vocabularies_are_searched(
    client: FlaskClient, member: SimpleNamespace
) -> None:
    def search(name: str, **query) -> list[dict]:
        response = client.get(
            f"/api/v1/vocabularies/values/{name}",
            query_string=query,
            headers=_auth(member.token),
        )
        return response.get_json()["items"]

    assert search("metier", search="cto") == [
        {"value": "Numérique / CTO", "label": "Numérique / CTO", "group": "Numérique"}
    ]
    assert [v["value"] for v in search("metier.groups")] == ["Numérique", "Santé"]
    assert [v["value"] for v in search("countries", search="bel")] == ["BEL"]
    assert [v["value"] for v in search("cities", country="FRA", search="meu")] == [
        MEUDON
    ]
    assert search("cities") == []
    types = client.get(
        "/api/v1/vocabularies/profile-types", headers=_auth(member.token)
    ).get_json()["items"]
    assert LEADER in [each["id"] for each in types]
