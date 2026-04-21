# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for the MVP matchmaking layer (Avis d'Enquête).

Covers:
- `match_experts_to_avis`: thematic + activity pre-filter, with fallback
- `partition_by_cap` / `experts_over_notification_cap`: anti-spam cap
- `record_notifications`: persists `AvisNotificationLog` rows
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import arrow
import pytest

from app.models.auth import KYCProfile, User
from app.models.organisation import Organisation
from app.modules.wip.models import AvisEnquete, AvisNotificationLog
from app.modules.wip.services.newsroom.avis_matching import (
    ACTIVITY_LOOKBACK_DAYS,
    NOTIFICATION_CAP,
    experts_over_notification_cap,
    match_experts_to_avis,
    partition_by_cap,
    record_notifications,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _mk_expert(
    db_session: Session,
    *,
    secteurs: list[str] | None = None,
    last_login_at: datetime | None = None,
) -> User:
    user = User(
        email=f"expert-{uuid.uuid4().hex[:6]}@example.com",
        first_name="Expert",
        last_name="T",
        active=True,
    )
    if last_login_at is not None:
        user.last_login_at = last_login_at  # type: ignore[assignment]
    db_session.add(user)
    db_session.flush()

    profile = KYCProfile(user_id=user.id)
    if secteurs is not None:
        profile.info_professionnelle = {
            "secteurs_activite_detailles_detail": list(secteurs),
        }
    db_session.add(profile)
    db_session.flush()
    return user


def _mk_avis(
    db_session: Session,
    *,
    journaliste: User,
    sector: str = "",
    ciblage_secteur_detailles: str = "",
) -> AvisEnquete:
    media = Organisation(name=f"Media-{uuid.uuid4().hex[:6]}")
    db_session.add(media)
    db_session.flush()

    avis = AvisEnquete(owner=journaliste)
    avis.titre = "Test Avis"
    avis.contenu = "Contenu minimal"
    avis.sector = sector
    avis.ciblage_secteur_detailles = ciblage_secteur_detailles
    avis.media_id = media.id
    avis.commanditaire_id = journaliste.id
    avis.date_debut_enquete = arrow.now("UTC").datetime
    avis.date_fin_enquete = arrow.now("UTC").shift(days=7).datetime
    avis.date_bouclage = arrow.now("UTC").shift(days=5).datetime
    avis.date_parution_prevue = arrow.now("UTC").shift(days=14).datetime
    db_session.add(avis)
    db_session.flush()
    return avis


@pytest.fixture
def journalist(db_session: Session) -> User:
    user = User(
        email=f"journ-{uuid.uuid4().hex[:6]}@example.com",
        first_name="Journ",
        last_name="T",
        active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


# ---------------------------------------------------------------------------
# match_experts_to_avis
# ---------------------------------------------------------------------------


class TestMatchExpertsToAvis:
    def test_keeps_only_active_experts_with_sector_match(
        self, db_session: Session, journalist: User
    ):
        recent = datetime.now(UTC) - timedelta(days=10)
        avis = _mk_avis(db_session, journaliste=journalist, sector="Économie")

        matching = [
            _mk_expert(
                db_session, secteurs=["Économie", "Finance"], last_login_at=recent
            )
            for _ in range(6)
        ]
        # Off-topic expert, should be excluded (enough matches without them)
        off_topic = _mk_expert(
            db_session, secteurs=["Sport"], last_login_at=recent
        )
        # Dormant expert on topic, excluded regardless
        dormant = _mk_expert(
            db_session,
            secteurs=["Économie"],
            last_login_at=datetime.now(UTC) - timedelta(days=365),
        )

        result = match_experts_to_avis(
            [*matching, off_topic, dormant], avis
        )

        result_ids = {e.id for e in result}
        assert {e.id for e in matching}.issubset(result_ids)
        assert off_topic.id not in result_ids
        assert dormant.id not in result_ids

    def test_fallback_when_too_few_matches(
        self, db_session: Session, journalist: User
    ):
        """If fewer than 5 sector-matches, fall back to the active pool."""
        recent = datetime.now(UTC) - timedelta(days=10)
        avis = _mk_avis(db_session, journaliste=journalist, sector="Nucléaire")

        one_match = _mk_expert(
            db_session, secteurs=["Nucléaire"], last_login_at=recent
        )
        off_topic_actives = [
            _mk_expert(
                db_session, secteurs=["Sport"], last_login_at=recent
            )
            for _ in range(3)
        ]
        dormant = _mk_expert(
            db_session,
            secteurs=["Nucléaire"],
            last_login_at=datetime.now(UTC) - timedelta(days=365),
        )

        pool = [one_match, *off_topic_actives, dormant]
        result = match_experts_to_avis(pool, avis)

        result_ids = {e.id for e in result}
        # Fallback: all active experts (including off-topic), but dormant
        # is still excluded by activity filter.
        assert one_match.id in result_ids
        for e in off_topic_actives:
            assert e.id in result_ids
        assert dormant.id not in result_ids

    def test_no_sector_metadata_returns_only_active(
        self, db_session: Session, journalist: User
    ):
        recent = datetime.now(UTC) - timedelta(days=10)
        avis = _mk_avis(db_session, journaliste=journalist, sector="")

        active = _mk_expert(
            db_session, secteurs=["Économie"], last_login_at=recent
        )
        dormant = _mk_expert(
            db_session,
            secteurs=["Économie"],
            last_login_at=datetime.now(UTC) - timedelta(days=365),
        )

        result = match_experts_to_avis([active, dormant], avis)

        result_ids = {e.id for e in result}
        assert active.id in result_ids
        assert dormant.id not in result_ids

    def test_ciblage_secteur_detailles_parsed(
        self, db_session: Session, journalist: User
    ):
        """Detailed sector list in a comma/semicolon string is parsed."""
        recent = datetime.now(UTC) - timedelta(days=10)
        avis = _mk_avis(
            db_session,
            journaliste=journalist,
            sector="",
            ciblage_secteur_detailles="Santé, Education; Culture",
        )

        in_sante = [
            _mk_expert(
                db_session, secteurs=["Santé"], last_login_at=recent
            )
            for _ in range(5)
        ]
        off_topic = _mk_expert(
            db_session, secteurs=["Sport"], last_login_at=recent
        )

        result = match_experts_to_avis([*in_sante, off_topic], avis)

        result_ids = {e.id for e in result}
        for e in in_sante:
            assert e.id in result_ids
        assert off_topic.id not in result_ids

    def test_expert_without_last_login_is_excluded(
        self, db_session: Session, journalist: User
    ):
        """Users who never logged in are considered dormant."""
        avis = _mk_avis(db_session, journaliste=journalist, sector="Économie")

        never_logged = _mk_expert(
            db_session, secteurs=["Économie"], last_login_at=None
        )
        five_ok = [
            _mk_expert(
                db_session,
                secteurs=["Économie"],
                last_login_at=datetime.now(UTC) - timedelta(days=5),
            )
            for _ in range(5)
        ]

        result = match_experts_to_avis([never_logged, *five_ok], avis)

        result_ids = {e.id for e in result}
        assert never_logged.id not in result_ids


# ---------------------------------------------------------------------------
# Anti-spam layer
# ---------------------------------------------------------------------------


def _log_notifications(
    db_session: Session, expert: User, n: int, days_ago: int = 1
) -> None:
    base = datetime.now(UTC) - timedelta(days=days_ago)
    for _ in range(n):
        db_session.add(
            AvisNotificationLog(user_id=expert.id, sent_at=base)
        )
    db_session.flush()


class TestAntiSpamCap:
    def test_no_history_returns_empty(
        self, db_session: Session
    ):
        recent = datetime.now(UTC) - timedelta(days=10)
        experts = [
            _mk_expert(db_session, secteurs=["X"], last_login_at=recent)
            for _ in range(3)
        ]
        assert experts_over_notification_cap(db_session, experts) == set()

    def test_experts_at_cap_are_reported(self, db_session: Session):
        recent = datetime.now(UTC) - timedelta(days=10)
        spammed = _mk_expert(
            db_session, secteurs=["X"], last_login_at=recent
        )
        clean = _mk_expert(
            db_session, secteurs=["X"], last_login_at=recent
        )
        _log_notifications(db_session, spammed, n=NOTIFICATION_CAP)

        over = experts_over_notification_cap(db_session, [spammed, clean])

        assert spammed.id in over
        assert clean.id not in over

    def test_old_notifications_outside_window_are_ignored(
        self, db_session: Session
    ):
        recent = datetime.now(UTC) - timedelta(days=10)
        expert = _mk_expert(
            db_session, secteurs=["X"], last_login_at=recent
        )
        _log_notifications(db_session, expert, n=NOTIFICATION_CAP, days_ago=40)

        over = experts_over_notification_cap(db_session, [expert])
        assert expert.id not in over

    def test_partition_splits_correctly(self, db_session: Session):
        recent = datetime.now(UTC) - timedelta(days=10)
        e1 = _mk_expert(db_session, secteurs=["X"], last_login_at=recent)
        e2 = _mk_expert(db_session, secteurs=["X"], last_login_at=recent)
        e3 = _mk_expert(db_session, secteurs=["X"], last_login_at=recent)
        _log_notifications(db_session, e2, n=NOTIFICATION_CAP)

        to_notify, skipped = partition_by_cap(db_session, [e1, e2, e3])

        assert {e.id for e in to_notify} == {e1.id, e3.id}
        assert [e.id for e in skipped] == [e2.id]


class TestRecordNotifications:
    def test_one_row_per_expert(
        self, db_session: Session, journalist: User
    ):
        avis = _mk_avis(db_session, journaliste=journalist, sector="X")
        e1 = _mk_expert(db_session, secteurs=["X"])
        e2 = _mk_expert(db_session, secteurs=["X"])

        record_notifications(db_session, [e1, e2], avis)
        db_session.flush()

        rows = db_session.query(AvisNotificationLog).all()
        assert {r.user_id for r in rows} == {e1.id, e2.id}
        assert all(r.avis_enquete_id == avis.id for r in rows)

    def test_record_then_cap_roundtrip(
        self, db_session: Session, journalist: User
    ):
        """Recording NOTIFICATION_CAP times should flip expert into 'over cap'."""
        avis = _mk_avis(db_session, journaliste=journalist, sector="X")
        expert = _mk_expert(db_session, secteurs=["X"])

        for _ in range(NOTIFICATION_CAP):
            record_notifications(db_session, [expert], avis)
        db_session.flush()

        over = experts_over_notification_cap(db_session, [expert])
        assert expert.id in over

    def test_record_with_null_avis(self, db_session: Session):
        expert = _mk_expert(db_session, secteurs=["X"])
        record_notifications(db_session, [expert], None)
        db_session.flush()

        row = db_session.query(AvisNotificationLog).one()
        assert row.user_id == expert.id
        assert row.avis_enquete_id is None


# ---------------------------------------------------------------------------
# Lookback boundary
# ---------------------------------------------------------------------------


def test_activity_lookback_uses_default_constant(db_session: Session, journalist: User):
    """Expert logged in just within the 180-day window remains eligible."""
    just_inside = datetime.now(UTC) - timedelta(
        days=ACTIVITY_LOOKBACK_DAYS - 1
    )
    just_outside = datetime.now(UTC) - timedelta(
        days=ACTIVITY_LOOKBACK_DAYS + 1
    )
    avis = _mk_avis(db_session, journaliste=journalist, sector="Économie")

    inside = _mk_expert(
        db_session, secteurs=["Économie"], last_login_at=just_inside
    )
    outside = _mk_expert(
        db_session, secteurs=["Économie"], last_login_at=just_outside
    )

    result = match_experts_to_avis([inside, outside], avis)
    result_ids = {e.id for e in result}
    assert inside.id in result_ids
    assert outside.id not in result_ids
