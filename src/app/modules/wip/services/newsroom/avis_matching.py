# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""MVP matchmaking helpers for Avis d'Enquête.

Kept intentionally small (see `local-notes/specs/matchmaking-avis-enquete.md`,
Phase 0 MVP):

1. `match_experts_to_avis(experts, avis)` — pre-scopes a candidate pool
   of experts to those with a thematic match and recent activity, with
   a graceful fallback if the match is too narrow.

2. `experts_over_notification_cap(session, experts, cap, days)` +
   `record_notifications(session, experts, avis)` — anti-spam layer
   backed by `AvisNotificationLog`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from app.models.auth import User
from app.modules.wip.models.newsroom.avis_notification_log import (
    AvisNotificationLog,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.modules.wip.models.newsroom.avis_enquete import AvisEnquete

ACTIVITY_LOOKBACK_DAYS = 180
MIN_CANDIDATES = 5
NOTIFICATION_CAP = 10
NOTIFICATION_WINDOW_DAYS = 30


def match_experts_to_avis(
    experts: list[User],
    avis: AvisEnquete,
    *,
    lookback_days: int = ACTIVITY_LOOKBACK_DAYS,
    min_candidates: int = MIN_CANDIDATES,
) -> list[User]:
    """Return the subset of `experts` relevant for this Avis.

    Rules (see Phase 0 spec §5.2):

    - Expert must have logged in in the last `lookback_days` days.
    - Expert's `secteurs_activite` must intersect the Avis's sector(s).
    - If fewer than `min_candidates` experts match on sector, fall back
      to the active-only pool (no sector filter).
    - If the Avis has no usable sector metadata, no thematic filter is
      applied, only the activity one.
    """
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=lookback_days)

    active = [e for e in experts if _is_active_recently(e, cutoff)]
    avis_sectors = _avis_sectors(avis)
    if not avis_sectors:
        return active

    matched = [e for e in active if _expert_sectors(e) & avis_sectors]
    if len(matched) < min_candidates:
        return active
    return matched


def experts_over_notification_cap(
    session: Session,
    experts: list[User],
    *,
    cap: int = NOTIFICATION_CAP,
    days: int = NOTIFICATION_WINDOW_DAYS,
) -> set[int]:
    """Return IDs of experts who have hit the notification cap.

    Counts notifications sent in the rolling window `[now - days, now]`.
    An expert with `count >= cap` is considered over cap and will be
    excluded from the next batch.
    """
    if not experts:
        return set()

    cutoff = datetime.now(UTC) - timedelta(days=days)
    user_ids = [e.id for e in experts]

    stmt = (
        select(AvisNotificationLog.user_id, func.count())
        .where(AvisNotificationLog.sent_at >= cutoff)
        .where(AvisNotificationLog.user_id.in_(user_ids))
        .group_by(AvisNotificationLog.user_id)
        .having(func.count() >= cap)
    )
    return {row[0] for row in session.execute(stmt)}


def partition_by_cap(
    session: Session,
    experts: list[User],
    *,
    cap: int = NOTIFICATION_CAP,
    days: int = NOTIFICATION_WINDOW_DAYS,
) -> tuple[list[User], list[User]]:
    """Split `experts` into (to_notify, skipped_due_to_cap)."""
    if _mail_debug_active():
        # The dev DB AvisNotificationLog accumulates across e2e runs ;
        # without this bypass the test that exercises the confirm
        # path systematically hits the cap on the second run.
        return list(experts), []
    over = experts_over_notification_cap(session, experts, cap=cap, days=days)
    if not over:
        return list(experts), []
    to_notify = [e for e in experts if e.id not in over]
    skipped = [e for e in experts if e.id in over]
    return to_notify, skipped


def _mail_debug_active() -> bool:
    """Local import — circular dep otherwise."""
    from app.lib.mail_debug import is_active

    return is_active()


def record_notifications(
    session: Session,
    experts: list[User],
    avis: AvisEnquete | None,
) -> None:
    """Persist one `AvisNotificationLog` row per expert.

    Called right after emails are dispatched. Keeping it synchronous
    means the anti-spam counter is accurate even if later processing
    fails.
    """
    avis_id = getattr(avis, "id", None)
    for expert in experts:
        session.add(AvisNotificationLog(user_id=expert.id, avis_enquete_id=avis_id))


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _is_active_recently(expert: User, cutoff: datetime) -> bool:
    last = expert.last_login_at
    if last is None:
        return False
    if last.tzinfo is None:
        last = last.replace(tzinfo=UTC)
    return last >= cutoff


def _avis_sectors(avis: AvisEnquete) -> set[str]:
    sectors: set[str] = set()
    primary = getattr(avis, "sector", "") or ""
    if primary:
        sectors.add(primary)
    detailled = getattr(avis, "ciblage_secteur_detailles", "") or ""
    for chunk in detailled.replace(";", ",").split(","):
        s = chunk.strip()
        if s:
            sectors.add(s)
    return sectors


def _expert_sectors(expert: User) -> set[str]:
    profile = expert.profile
    if profile is None:
        return set()
    return {s for s in profile.secteurs_activite if s}
