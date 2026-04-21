# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""SQLAlchemy event hooks for the Wire module.

- `_snapshot_rights_policy_on_publish`: freezes the emitter BW's
  cession-de-droits policy onto the Post the first time it reaches
  `PublicationStatus.PUBLIC`. Non-retroactive — subsequent updates
  never overwrite the snapshot.
"""

from __future__ import annotations

import sqlalchemy as sa
import sqlalchemy.event
from sqlalchemy.orm import attributes

from app.models.lifecycle import PublicationStatus
from app.modules.wire.models import Post


def _status_transitions_to_public(target: Post) -> bool:
    """Return True if this flush turns the Post from non-PUBLIC → PUBLIC."""
    history = attributes.get_history(target, "status")
    if not history.has_changes():
        # On insert, value is in `.added` without prior recorded history;
        # decide based on the current value.
        return target.status == PublicationStatus.PUBLIC
    if target.status != PublicationStatus.PUBLIC:
        return False
    # An update: look at what was there before.
    previous = history.deleted[0] if history.deleted else None
    return previous != PublicationStatus.PUBLIC


def _freeze_policy(target: Post) -> None:
    if target.rights_sales_snapshot is not None:
        return
    from app.modules.bw.bw_activation.rights_policy import (
        emitter_bw_for_post,
        snapshot_policy_for,
    )

    bw = emitter_bw_for_post(target)
    target.rights_sales_snapshot = snapshot_policy_for(bw)


@sa.event.listens_for(Post, "before_update", propagate=True)
def _snapshot_rights_policy_on_update(_mapper, _connection, target: Post) -> None:
    if _status_transitions_to_public(target):
        _freeze_policy(target)


@sa.event.listens_for(Post, "before_insert", propagate=True)
def _snapshot_rights_policy_on_insert(_mapper, _connection, target: Post) -> None:
    if target.status == PublicationStatus.PUBLIC:
        _freeze_policy(target)
