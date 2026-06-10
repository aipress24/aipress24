# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Stage 6: Missions/permissions assignment routes."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from flask import g, redirect, render_template, request, session, url_for

from app.flask.extensions import db
from app.logging import warn
from app.models.auth import User
from app.modules.bw.bw_activation import bp
from app.modules.bw.bw_activation.bw_invitation import sync_all_pr_missions
from app.modules.bw.bw_activation.config import BW_TYPES
from app.modules.bw.bw_activation.models.role import PermissionType
from app.modules.bw.bw_activation.user_utils import current_business_wall
from app.modules.bw.bw_activation.utils import (
    ERR_BW_NOT_FOUND,
    ERR_NOT_MANAGER,
    fill_session,
    init_missions_state,
    is_bw_manager_or_admin,
)

# Mapping of form-field name -> PermissionType value, used by
# `parse_missions_from_form` to translate the HTML checkbox names from
# the B06 template into the canonical permission keys persisted on
# `BusinessWall.missions`. Lifted to module scope so the pure helper
# can be unit-tested without rebuilding the dict on each request and
# so the contract (which checkboxes drive which permission) is
# visible at a glance.
_FORM_TO_PERMISSION: dict[str, str] = {
    "mission_press_release": PermissionType.PRESS_RELEASE.value,
    "mission_events": PermissionType.EVENTS.value,
    "mission_missions": PermissionType.MISSIONS.value,
    "mission_projects": PermissionType.PROJECTS.value,
    "mission_internships": PermissionType.INTERNSHIPS.value,
    "mission_apprenticeships": PermissionType.APPRENTICESHIPS.value,
    "mission_doctoral": PermissionType.DOCTORAL.value,
}

# The action keyword on the stage-B6 form submit button. Only these
# two values are recognised — anything else is a programmer error
# (the template can't emit something else without an edit) and the
# route raises ``ValueError`` rather than silently defaulting.
_VALID_ACTIONS: frozenset[str] = frozenset({"previous", "finish"})


def parse_missions_from_form(form: Mapping[str, Any]) -> dict[str, bool]:
    """Pure: translate a request.form mapping into the missions dict.

    Each entry of ``_FORM_TO_PERMISSION`` is checked: a present, truthy
    value yields ``True``; an absent or empty value yields ``False``.

    Args:
        form: A mapping that behaves like Flask's ``request.form`` — the
            real ``ImmutableMultiDict`` works, as does any plain ``dict``.
            We deliberately type as ``Mapping`` so tests can pass plain
            dicts without flask machinery.

    Returns:
        A dict keyed by ``PermissionType`` value (``"press_release"``,
        ``"events"``, …) with boolean values reflecting the form state.
        Permission types absent from the form mapping are mapped to
        ``False`` — checkboxes do not POST a value when unchecked.
    """
    return {
        permission: bool(form.get(field))
        for field, permission in _FORM_TO_PERMISSION.items()
    }


def diff_missions(
    before: Mapping[str, bool], after: Mapping[str, bool]
) -> tuple[set[str], set[str]]:
    """Pure: compute (granted, revoked) permissions between two states.

    Returns the set of permission keys that flipped from
    ``False``/missing -> ``True`` (granted) and from ``True`` ->
    ``False``/missing (revoked).

    Permissions absent from either mapping are treated as ``False``.
    Permissions whose state did not change appear in neither set.

    Args:
        before: The previous missions dict (``BusinessWall.missions``
            before this POST).
        after: The new missions dict produced by
            :func:`parse_missions_from_form`.

    Returns:
        ``(granted, revoked)`` — two sets of permission-type keys.
    """
    all_keys = set(before) | set(after)
    granted: set[str] = set()
    revoked: set[str] = set()
    for key in all_keys:
        was = bool(before.get(key, False))
        is_now = bool(after.get(key, False))
        if was and not is_now:
            revoked.add(key)
        elif is_now and not was:
            granted.add(key)
    return granted, revoked


def resolve_previous_endpoint(bw_type: str) -> str:
    """Pure: pick the « previous » route name for the stage-B6 form.

    The B6 wizard step is preceded by *manage_internal_roles* for PR
    (``"pr"``) Business Walls and by *manage_external_partners* for
    every other BW type. Extracted so the branch is independently
    testable.

    Args:
        bw_type: The current BW's type string (``"pr"``, ``"media"``,
            …).

    Returns:
        The fully-qualified Flask endpoint to redirect to.
    """
    if bw_type == "pr":
        return "bw_activation.manage_internal_roles"
    return "bw_activation.manage_external_partners"


def is_valid_action(action: str) -> bool:
    """Pure: ``True`` iff ``action`` is one of ``previous`` / ``finish``.

    Centralises the action whitelist so the route guard and any test
    that wants to assert « no silent default » share a single source.
    """
    return action in _VALID_ACTIONS


@bp.route("/assign-missions", methods=["GET", "POST"])
def assign_missions():
    """Stage B6: Assign permissions/missions to PR Managers."""
    # at this stage the BW must be created
    user = cast(User, g.user)

    business_wall = current_business_wall(user)
    if not business_wall:
        session["error"] = ERR_BW_NOT_FOUND
        return redirect(url_for("bw_activation.not_authorized"))
    fill_session(business_wall)
    if not is_bw_manager_or_admin(user, business_wall):
        session["error"] = ERR_NOT_MANAGER
        return redirect(url_for("bw_activation.not_authorized"))

    if not session.get("bw_activated") or not session.get("bw_type"):
        return redirect(url_for("bw_activation.index"))

    bw_type: str = cast(str, session["bw_type"])
    bw_info: dict[str, Any] = BW_TYPES.get(bw_type, {})

    if not session.get("bw_activated"):
        return redirect(url_for("bw_activation.index"))

    missions: dict[str, bool] = {}
    if business_wall.missions:
        missions = cast(dict[str, bool], business_wall.missions)
        session["missions"] = missions
    else:
        init_missions_state()

    if request.method == "POST":
        # Update missions from form data (pure parser; see helpers above)
        missions = parse_missions_from_form(request.form)

        # Save to BusinessWall
        business_wall.missions = missions

        # sync missions to allcurrent PR users
        sync_all_pr_missions(business_wall)

        db.session.commit()

        # Also update session for UI consistency
        session["missions"] = missions

        warn(missions)

        # Determine redirect based on button clicked
        action = request.form.get("action", "finish")
        warn(action)

        if not is_valid_action(action):
            msg = f"Unknown action {action!r}"
            warn(msg)
            raise ValueError(msg)

        if action == "previous":
            return redirect(url_for(resolve_previous_endpoint(bw_type)))
        return redirect(url_for("bw_activation.dashboard"))

    return render_template(
        "bw_activation/B06_assign_missions.html",
        bw_type=bw_type,
        bw_info=bw_info,
        missions=session["missions"],
    )
