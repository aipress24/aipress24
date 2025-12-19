# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin user validation views."""

from __future__ import annotations

import sys
import uuid
from datetime import UTC, datetime
from typing import Any

from arrow import now
from flask import Response, render_template, request, url_for
from loguru import logger

from app.constants import (
    LABEL_INSCRIPTION_VALIDEE,
    LABEL_MODIFICATION_VALIDEE,
    LOCAL_TZ,
)
from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.flask.sqla import get_obj
from app.models.auth import User, merge_values_from_other_user
from app.modules.admin import blueprint
from app.modules.admin.utils import gc_all_auto_organisations
from app.modules.kyc.organisation_utils import retrieve_user_organisation
from app.modules.kyc.views import admin_info_context


def _detect_business_wall_trigger(user: User, context: dict[str, Any]) -> None:
    """Detect business wall trigger for user."""
    media_status = {"bw_trigger": False, "bw_organisation": ""}
    profile = user.profile
    trigger = profile.get_first_bw_trigger()
    if trigger:
        media_status = {
            "bw_trigger": True,
            "bw_organisation": user.organisation_name or "aucune?",
        }
    context.update(media_status)


@blueprint.route("/validation_profile/<uid>")
@nav(parent="new_users", icon="check-circle", label="Validation inscription")
def validation_user(uid: str):
    """User validation page."""
    user = get_obj(uid, User)
    context = admin_info_context(user)
    _detect_business_wall_trigger(user, context)
    context.update({
        "user": user,
        "title": "Validation de l'inscription",
    })
    return render_template("admin/pages/validation_user.j2", **context)


@blueprint.route("/validation_profile/<uid>", methods=["POST"])
@nav(hidden=True)
def validation_user_post(uid: str):
    """Handle user validation POST actions."""
    user = get_obj(uid, User)
    action = request.form.get("action")

    if action == "validate":
        _validate_profile(user)
    elif action == "reject":
        _reject_profile(user)

    response = Response("")
    response.headers["HX-Redirect"] = url_for("admin.new_users")
    return response


def _validate_profile(user: User) -> None:
    """Validate user profile - either new or modified."""
    if user.email_safe_copy:
        _validate_profile_modified(user)
    else:
        _validate_profile_created(user)


def _reject_profile(user: User) -> None:
    """Reject user profile."""
    user.deleted_at = now(LOCAL_TZ)
    user.active = False
    # Free the rejected user email (unique field)
    user.email = f"fake_{uuid.uuid4().hex}@example.com"

    db.session.merge(user)
    db.session.commit()

    msg = f"User marked as deleted {user.id} {user.email}"
    logger.info(msg)
    print(msg, file=sys.stderr)

    # Clean up orphan auto organisations
    gc_all_auto_organisations()
    db.session.commit()


def _validate_profile_modified(user: User) -> None:
    """Validate modified profile (user is a clone)."""
    orig_user = get_obj(user.cloned_user_id, User)
    merge_values_from_other_user(orig_user, user)

    auto_organisation = retrieve_user_organisation(orig_user)
    if auto_organisation:
        orig_user.organisation_id = auto_organisation.id

    orig_user.validation_status = LABEL_MODIFICATION_VALIDEE
    orig_user.active = True
    orig_user.validated_at = datetime.now(UTC)

    db.session.merge(orig_user)
    db.session.delete(user)
    db.session.commit()

    # Clean up orphan auto organisations
    gc_all_auto_organisations()
    db.session.commit()


def _validate_profile_created(user: User) -> None:
    """Validate newly created profile."""
    auto_organisation = retrieve_user_organisation(user)
    if auto_organisation:
        user.organisation_id = auto_organisation.id

    user.active = True
    user.validation_status = LABEL_INSCRIPTION_VALIDEE
    user.validated_at = now(LOCAL_TZ)

    db.session.merge(user)
    db.session.commit()
