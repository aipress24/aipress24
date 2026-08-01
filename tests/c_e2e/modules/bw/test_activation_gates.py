# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Qui peut entrer dans le tunnel d'activation d'un Business Wall.

Deux refus, tous deux constatés en production :

- ticket 0273 : Erwann Le Fur, étudiant en journalisme, arrivait sur
  l'initialisation d'un « Business Wall for Journalist ». L'abonnement
  appartient à l'établissement, pas à ses étudiants.
- ticket 0271 : Martine Riesser, après avoir quitté son organisation,
  traversait tout le tunnel pour mourir juste avant Stripe sur « aucune
  organisation trouvée », sans rien à faire de cette information.

Les deux gardes s'appliquent aux points d'entrée du tunnel, pas au
blueprint : un utilisateur peut n'avoir ni organisation ni droit
d'ouvrir un BW tout en détenant un rôle sur le BW d'un tiers, dont le
tableau de bord doit rester accessible.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.enums import ProfileEnum
from app.models.auth import KYCProfile, User
from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


def _make_user(
    db_session: Session,
    *,
    email: str,
    first_name: str,
    last_name: str,
    profile_code: ProfileEnum,
) -> User:
    """A logged-in-able user with a KYC profile and no organisation."""
    user = User(email=email, first_name=first_name, last_name=last_name, active=True)
    db_session.add(user)
    db_session.flush()
    db_session.add(
        KYCProfile(
            user_id=user.id,
            profile_id=f"profile_{profile_code.name.lower()}",
            profile_code=profile_code.value,
            profile_label=profile_code.name,
        )
    )
    db_session.flush()
    return user


class TestStudentsCannotOpenABusinessWall:
    """Ticket 0273."""

    @pytest.fixture
    def student_client(self, app: Flask, db, db_session: Session) -> FlaskClient:
        student = _make_user(
            db_session,
            email="erwann.lefur@example.com",
            first_name="Erwann",
            last_name="Le Fur",
            profile_code=ProfileEnum.AC_ST,
        )
        return make_authenticated_client(app, student)

    def test_redirected_away_from_the_funnel(self, student_client: FlaskClient):
        response = student_client.get("/BW/")

        assert response.status_code in (302, 303)
        assert "/BW/not-authorized" in response.headers["Location"]

    def test_gets_an_explanation(self, student_client: FlaskClient):
        body = student_client.get("/BW/", follow_redirects=True).data.decode()

        assert "rapprochez-vous de votre établissement" in body

    def test_cannot_jump_straight_to_the_subscription_page(
        self, student_client: FlaskClient
    ):
        """The funnel is reachable by URL, so its own entry point guards
        too — otherwise the redirect on /BW/ is decorative."""
        response = student_client.get("/BW/confirm-subscription")

        assert response.status_code in (302, 303)
        assert "/BW/not-authorized" in response.headers["Location"]

    def test_cannot_post_a_subscription_choice(self, student_client: FlaskClient):
        """`select-subscription` is the POST that unlocks the rest of the
        funnel by setting `bw_type_confirmed`."""
        response = student_client.post("/BW/select-subscription/micro")

        assert response.status_code in (302, 303)
        assert "/BW/not-authorized" in response.headers["Location"]

    def test_a_professional_still_reaches_the_funnel(
        self, authenticated_owner_client: FlaskClient
    ):
        """The gate must not catch legitimate profiles."""
        response = authenticated_owner_client.get("/BW/confirm-subscription")

        assert response.status_code == 200


class TestOrganisationlessUserIsSentToTheKyc:
    """Ticket 0271."""

    @pytest.fixture
    def orphan_client(self, app: Flask, db, db_session: Session) -> FlaskClient:
        """An eligible professional who just left their organisation."""
        martine = _make_user(
            db_session,
            email="martine.riesser@example.com",
            first_name="Martine",
            last_name="Riesser",
            profile_code=ProfileEnum.PM_JR_ME,
        )
        assert martine.organisation is None
        return make_authenticated_client(app, martine)

    def test_stopped_at_the_funnel_entry(self, orphan_client: FlaskClient):
        """The refusal must come at the start, not four screens later at
        the payment step."""
        response = orphan_client.get("/BW/")

        assert response.status_code in (302, 303)
        assert "/BW/not-authorized" in response.headers["Location"]

    def test_told_what_to_do(self, orphan_client: FlaskClient):
        body = orphan_client.get("/BW/", follow_redirects=True).data.decode()

        assert "Indiquez le nom de votre organisation dans votre profil" in body

    def test_offered_a_link_to_the_kyc(self, orphan_client: FlaskClient):
        """An explanation the user cannot act on is the bug we are fixing."""
        body = orphan_client.get("/BW/", follow_redirects=True).data.decode()

        assert "/kyc/modify" in body
        assert "Renseigner mon organisation" in body

    def test_cannot_jump_straight_into_the_funnel(self, orphan_client: FlaskClient):
        response = orphan_client.get("/BW/confirm-subscription")

        assert response.status_code in (302, 303)
        assert "/BW/not-authorized" in response.headers["Location"]

    def test_cannot_post_a_subscription_choice(self, orphan_client: FlaskClient):
        response = orphan_client.post("/BW/select-subscription/micro")

        assert response.status_code in (302, 303)
        assert "/BW/not-authorized" in response.headers["Location"]

    def test_a_user_with_an_organisation_still_reaches_the_funnel(
        self, authenticated_owner_client: FlaskClient
    ):
        response = authenticated_owner_client.get("/BW/confirm-subscription")

        assert response.status_code == 200
