# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Ticket #0195 — the « Justificatif » action on a published article
opens a form to notify the enquête participants. POST sends mails +
cloches via `notify_avis_participants_of_justificatif`."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import patch

import arrow
import pytest

from app.flask.routing import url_for
from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.wip.models import Article
from app.modules.wip.models.newsroom.avis_enquete import (
    AvisEnquete,
    ContactAvisEnquete,
)
from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from flask import Flask


def _email() -> str:
    return f"art_{uuid.uuid4().hex[:6]}@example.com"


@pytest.fixture
def published_article(fresh_db, test_user: User, test_org: Organisation) -> Article:
    db = fresh_db.session
    now_arrow = arrow.utcnow()
    # WIP `Article` exposes `title` as a read-only property over the
    # stored `titre` column. Several `nrm_article` columns are NOT NULL.
    a = Article(
        titre="Article publié",
        owner_id=test_user.id,
        publisher_id=test_org.id,
        commanditaire_id=test_user.id,
        media_id=test_org.id,
        status=PublicationStatus.PUBLIC,
        published_at=now_arrow,
        date_parution_prevue=now_arrow,
    )
    db.add(a)
    db.commit()
    return a


@pytest.fixture
def avis_with_contacts(
    fresh_db, test_user: User, test_org: Organisation
) -> tuple[AvisEnquete, User]:
    db = fresh_db.session
    now = datetime.now(UTC)
    avis = AvisEnquete(
        titre="Enquête testée",
        contenu="...",
        owner_id=test_user.id,
        media_id=test_org.id,
        commanditaire_id=test_user.id,
        date_debut_enquete=now - timedelta(days=7),
        date_fin_enquete=now,
        date_bouclage=now + timedelta(days=7),
        date_parution_prevue=now + timedelta(days=14),
    )
    db.add(avis)
    db.commit()
    expert = User(email=_email(), first_name="Expert", last_name="Z", active=True)
    db.add(expert)
    db.commit()
    db.add(
        ContactAvisEnquete(
            avis_enquete_id=avis.id,
            journaliste_id=test_user.id,
            expert_id=expert.id,
        )
    )
    db.commit()
    return avis, expert


class TestNotifyForm:
    def test_get_renders_picker_with_journalist_avis(
        self,
        app: Flask,
        test_user: User,
        published_article: Article,
        avis_with_contacts: tuple[AvisEnquete, User],
    ):
        avis, _expert = avis_with_contacts
        client = make_authenticated_client(app, test_user)
        response = client.get(
            url_for("ArticlesWipView:notify", id=published_article.id)
        )
        assert response.status_code == 200
        body = response.data.decode()
        # The form must surface the journalist's avis as a choice.
        assert avis.titre in body
        # And before any avis is selected, contacts are not listed.
        assert "Aucun participant trouvé" not in body  # avis NOT yet picked
        assert "Sélectionnez d'abord une enquête" in body

    def test_get_with_selected_avis_lists_contacts(
        self,
        app: Flask,
        test_user: User,
        published_article: Article,
        avis_with_contacts: tuple[AvisEnquete, User],
    ):
        avis, expert = avis_with_contacts
        client = make_authenticated_client(app, test_user)
        response = client.get(
            url_for(
                "ArticlesWipView:notify",
                id=published_article.id,
                avis_enquete_id=avis.id,
            )
        )
        assert response.status_code == 200
        body = response.data.decode()
        assert expert.full_name in body

    def test_post_triggers_notifications(
        self,
        app: Flask,
        test_user: User,
        published_article: Article,
        avis_with_contacts: tuple[AvisEnquete, User],
    ):
        avis, expert = avis_with_contacts
        client = make_authenticated_client(app, test_user)

        with patch(
            "app.modules.wip.services.newsroom.justificatif_notification"
            ".notify_avis_participants_of_justificatif"
        ) as mock_notify:
            mock_notify.return_value = 1
            response = client.post(
                url_for("ArticlesWipView:notify", id=published_article.id),
                data={
                    "avis_enquete_id": str(avis.id),
                    "recipient_user_id": [str(expert.id)],
                },
                follow_redirects=False,
            )

        assert response.status_code in (302, 303)
        # `notify_avis_participants_of_justificatif` was called with
        # the selected avis + the recipient.
        assert mock_notify.called
        kwargs = mock_notify.call_args.kwargs
        assert kwargs["recipient_user_ids"] == [expert.id]
        assert kwargs["avis_enquete"].id == avis.id
        assert kwargs["article"].id == published_article.id

    def test_post_without_avis_flashes_error(
        self,
        app: Flask,
        test_user: User,
        published_article: Article,
    ):
        client = make_authenticated_client(app, test_user)
        response = client.post(
            url_for("ArticlesWipView:notify", id=published_article.id),
            data={},
            follow_redirects=False,
        )
        # Redirect back to the form ; no notification sent.
        assert response.status_code in (302, 303)
        with client.session_transaction() as sess:
            flashes = sess.get("_flashes") or []
            messages = [m for _c, m in flashes]
            assert any("au moins un destinataire" in m for m in messages)

    def test_post_on_someone_elses_avis_refused(
        self,
        app: Flask,
        fresh_db,
        test_user: User,
        test_org: Organisation,
        published_article: Article,
        avis_with_contacts: tuple[AvisEnquete, User],
    ):
        """A journalist must not be able to trigger notifications for
        an avis owned by another journalist (even if they pass the id)."""
        db = fresh_db.session
        other = User(email=_email(), first_name="Other", last_name="Other", active=True)
        db.add(other)
        db.commit()
        now = datetime.now(UTC)
        foreign_avis = AvisEnquete(
            titre="Other's enquête",
            contenu="",
            owner_id=other.id,
            media_id=test_org.id,
            commanditaire_id=other.id,
            date_debut_enquete=now - timedelta(days=7),
            date_fin_enquete=now,
            date_bouclage=now + timedelta(days=7),
            date_parution_prevue=now + timedelta(days=14),
        )
        db.add(foreign_avis)
        db.commit()

        _avis, expert = avis_with_contacts
        client = make_authenticated_client(app, test_user)
        with patch(
            "app.modules.wip.services.newsroom.justificatif_notification"
            ".notify_avis_participants_of_justificatif"
        ) as mock_notify:
            response = client.post(
                url_for("ArticlesWipView:notify", id=published_article.id),
                data={
                    "avis_enquete_id": str(foreign_avis.id),
                    "recipient_user_id": [str(expert.id)],
                },
                follow_redirects=False,
            )
        # Refused → redirect with error flash, notify never called.
        assert response.status_code in (302, 303)
        mock_notify.assert_not_called()
