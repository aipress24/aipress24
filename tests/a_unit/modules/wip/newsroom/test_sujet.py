# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Bug 0132: tests for sujet publication workflow.

Before this fix `SujetsWipView` had no publish action, so journalists' sujet
proposals stayed in DRAFT forever and the targeted media never received
anything. This module covers:

- Sujet.publish() / unpublish() lifecycle on the model.
- SujetsTable.get_actions() exposes "Publier" / "Dépublier" depending on status.
- notify_media_of_sujet_proposition() routes the email to the media's BW owner.
"""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.wip.crud.cbvs.sujets import SujetsTable
from app.modules.wip.models.newsroom.sujet import Sujet
from app.modules.wip.services.sujet_notifications import (
    notify_media_of_sujet_proposition,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@pytest.fixture
def media_org(db_session: Session) -> Organisation:
    org = Organisation(name="Fake-01 Flounet")
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def author_user(db_session: Session) -> User:
    user = User(email="nicolas@example.com", first_name="Nicolas", last_name="Moriou")
    db_session.add(user)
    db_session.flush()
    return user


def _make_sujet(
    db_session: Session,
    *,
    media_id: int,
    owner_id: int,
    titre: str = "Mon enquête",
    contenu: str = "Brief de l'enquête",
    status: PublicationStatus = PublicationStatus.DRAFT,
) -> Sujet:
    sujet = Sujet(
        titre=titre,
        contenu=contenu,
        date_limite_validite=dt.datetime(2026, 12, 31, tzinfo=dt.UTC),
        date_parution_prevue=dt.datetime(2027, 1, 31, tzinfo=dt.UTC),
        media_id=media_id,
        owner_id=owner_id,
        commanditaire_id=owner_id,
    )
    sujet.status = status  # type: ignore[assignment]
    db_session.add(sujet)
    db_session.flush()
    return sujet


class TestSujetPublishLifecycle:
    def test_can_publish_in_draft_status(
        self, db_session: Session, media_org: Organisation, author_user: User
    ):
        sujet = _make_sujet(db_session, media_id=media_org.id, owner_id=author_user.id)
        assert sujet.can_publish() is True

    def test_publish_moves_to_public(
        self, db_session: Session, media_org: Organisation, author_user: User
    ):
        sujet = _make_sujet(db_session, media_id=media_org.id, owner_id=author_user.id)
        sujet.publish()
        assert sujet.status == PublicationStatus.PUBLIC

    def test_publish_idempotency_raises(
        self, db_session: Session, media_org: Organisation, author_user: User
    ):
        sujet = _make_sujet(
            db_session,
            media_id=media_org.id,
            owner_id=author_user.id,
            status=PublicationStatus.PUBLIC,
        )
        with pytest.raises(ValueError, match="DRAFT"):
            sujet.publish()

    def test_publish_requires_title(
        self, db_session: Session, media_org: Organisation, author_user: User
    ):
        sujet = _make_sujet(
            db_session, media_id=media_org.id, owner_id=author_user.id, titre=""
        )
        with pytest.raises(ValueError, match="titre"):
            sujet.publish()

    def test_publish_requires_content(
        self, db_session: Session, media_org: Organisation, author_user: User
    ):
        sujet = _make_sujet(
            db_session, media_id=media_org.id, owner_id=author_user.id, contenu=""
        )
        with pytest.raises(ValueError, match="contenu"):
            sujet.publish()

    def test_unpublish_returns_to_draft(
        self, db_session: Session, media_org: Organisation, author_user: User
    ):
        sujet = _make_sujet(db_session, media_id=media_org.id, owner_id=author_user.id)
        sujet.publish()

        sujet.unpublish()

        assert sujet.status == PublicationStatus.DRAFT

    def test_unpublish_only_from_public(
        self, db_session: Session, media_org: Organisation, author_user: User
    ):
        sujet = _make_sujet(db_session, media_id=media_org.id, owner_id=author_user.id)
        with pytest.raises(ValueError, match="PUBLIC"):
            sujet.unpublish()


class TestSujetsTableActions:
    def test_draft_item_shows_publier(self):
        table = SujetsTable()
        item = MagicMock(id=1, status=PublicationStatus.DRAFT)

        labels = [a["label"] for a in table.get_actions(item)]

        assert "Publier" in labels
        assert "Dépublier" not in labels

    def test_public_item_shows_depublier(self):
        table = SujetsTable()
        item = MagicMock(id=1, status=PublicationStatus.PUBLIC)

        labels = [a["label"] for a in table.get_actions(item)]

        assert "Dépublier" in labels
        assert "Publier" not in labels

    def test_core_actions_always_present(self):
        table = SujetsTable()
        item = MagicMock(id=1, status=PublicationStatus.DRAFT)

        labels = [a["label"] for a in table.get_actions(item)]

        assert "Voir" in labels
        assert "Modifier" in labels
        assert "Supprimer" in labels


class TestNotifyMediaOfSujetProposition:
    def test_skips_when_author_belongs_to_target_media(self, monkeypatch):
        sent = []

        def fake_send(self):
            sent.append(self)

        monkeypatch.setattr(
            "app.modules.wip.services.sujet_notifications."
            "SujetPropositionNotificationMail.send",
            fake_send,
            raising=True,
        )
        author = SimpleNamespace(organisation_id=42, email="j@x", full_name="Jane Doe")
        media_org = SimpleNamespace(id=42, bw_name="Same media", name="X")

        notify_media_of_sujet_proposition(
            author=author,
            media_org=media_org,
            sujet_title="Hello",
            sujet_url="https://x/sujet/1",
        )

        assert sent == []

    def test_skips_when_no_recipient_resolved(self, monkeypatch):
        sent = []

        def fake_send(self):
            sent.append(self)

        monkeypatch.setattr(
            "app.modules.wip.services.sujet_notifications."
            "SujetPropositionNotificationMail.send",
            fake_send,
            raising=True,
        )
        # _pick_bw_owner_email returns "" because no BW + no members.
        monkeypatch.setattr(
            "app.modules.wip.services.sujet_notifications._pick_bw_owner_email",
            lambda media_org: "",
        )
        author = SimpleNamespace(organisation_id=1, email="j@x", full_name="Jane")
        media_org = SimpleNamespace(id=99, bw_name="Empty media", name="X")

        notify_media_of_sujet_proposition(
            author=author,
            media_org=media_org,
            sujet_title="Hello",
            sujet_url="https://x/sujet/1",
        )

        assert sent == []

    def test_sends_when_bw_owner_resolved(self, monkeypatch):
        sent = []

        def fake_send(self):
            sent.append(self)

        monkeypatch.setattr(
            "app.modules.wip.services.sujet_notifications."
            "SujetPropositionNotificationMail.send",
            fake_send,
            raising=True,
        )
        monkeypatch.setattr(
            "app.modules.wip.services.sujet_notifications._pick_bw_owner_email",
            lambda media_org: "rc@flounet.example",
        )
        author = SimpleNamespace(
            organisation_id=1, email="nicolas@example", full_name="Nicolas Moriou"
        )
        media_org = SimpleNamespace(id=99, bw_name="Fake-01 Flounet", name="01F")

        notify_media_of_sujet_proposition(
            author=author,
            media_org=media_org,
            sujet_title="L'IA dans la supply chain",
            sujet_url="https://aipress24.com/wip/sujets/12",
        )

        assert len(sent) == 1
        mail = sent[0]
        assert mail.recipient == "rc@flounet.example"
        assert mail.media_name == "Fake-01 Flounet"
        assert mail.sujet_title == "L'IA dans la supply chain"
        assert mail.sender_full_name == "Nicolas Moriou"
