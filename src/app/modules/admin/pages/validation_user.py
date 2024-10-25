# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from typing import Any

from arrow import now
from flask import Response, g, request
from loguru import logger

from app.constants import (
    LABEL_INSCRIPTION_VALIDEE,
    LABEL_MODIFICATION_VALIDEE,
    LOCAL_TZ,
)
from app.flask.extensions import db
from app.flask.lib.pages import page
from app.flask.sqla import get_obj
from app.models.auth import User, merge_values_from_other_user
from app.modules.kyc.organisation_utils import store_user_auto_organisation
from app.modules.kyc.views import admin_info_context

from .. import blueprint
from .base import BaseAdminPage
from .new_users import AdminNewUsersPage


@page
class ValidationUser(BaseAdminPage):
    name = "valisate_user"
    path = "/validation_profile/<uid>"
    label = "Validation de l'inscription"
    title = "Validation de l'inscription"
    template = "admin/pages/validation_user.j2"
    parent = AdminNewUsersPage

    def __init__(self, uid: str = ""):
        if not uid:  # test
            uid = str(g.user.id)
        self.args = {"uid": uid}
        # options = selectinload(User.organisation)
        # self.user = get_obj(id, User, options=options)
        self.user = get_obj(uid, User)

    # def detect_direction_media_status(self, context: dict[str, Any]) -> None:
    #     """Detect if the validated user as status of Direction :
    #     - from declared profile (Dirigean Média, Dirigenta Média instit?)
    #     OR
    #     - from "fonction du journalisme" + profil Média
    #       - Dir de la publication
    #       - Dir a/s carte de presse AP/Média
    #       - Rédact chef
    #     AND check business wall trigger
    #     """
    #     media_satus = {"direction_media": False, "direction_media_comment": ""}
    #     is_direction = False
    #     is_media = False
    #     is_trigger = False

    #     profile = self.user.profile

    #     if (profile.profile_label in DIRECTION_PROFILE_LABELS) or (
    #         profile.get_first_value("fonctions_journalisme")
    #         in DIRECTION_FONCTIONS_JOURNALISME
    #     ):
    #         is_direction = True

    #     nom_media = profile.get_first_value("nom_media")
    #     if nom_media:
    #         is_media = True

    #     if profile.get_value("trigger_media_agence_de_presse") or profile.get_value(
    #         "trigger_media_media"
    #     ):
    #         is_trigger = True

    #     if is_direction and is_media and is_trigger:
    #         media_satus = {
    #             "direction_media": True,
    #             "direction_media_comment": f'Direction du média: "{nom_media}"',
    #         }
    #     context.update(media_satus)

    def detect_business_wall_trigger(self, context: dict[str, Any]) -> None:
        media_satus = {"bw_trigger": False, "bw_organisation": ""}
        profile = self.user.profile
        trigger = profile.get_first_bw_trigger()
        if trigger:
            media_satus = {
                "bw_trigger": True,
                "bw_organisation": self.user.organisation_name or "aucune?",
            }
        context.update(media_satus)

    def context(self):
        context = admin_info_context(self.user)
        self.detect_business_wall_trigger(context)
        context.update(
            {
                "user": self.user,
            }
        )
        return context

    def post(self):
        action = request.form.get("action")
        if action == "validate":
            self._validate_profile()
        if action == "reject":
            self._reject_profile()
        # no validation
        response = Response("")
        response.headers["HX-Redirect"] = AdminNewUsersPage().url
        return response

    def _validate_profile(self) -> None:
        # either a clone (modification) or plain user (creation)
        if self.user.email_safe_copy:
            self._validate_profile_modified()
        else:
            self._validate_profile_created()

    def _reject_profile(self) -> None:
        # shoud not be a clone: a plain new user (creation)
        self.user.deleted_at = now(LOCAL_TZ)
        self.user.active = False
        # we need to free the rejectd user email because
        # it's a 'unique' field'
        self.user.email = f"fake_{uuid.uuid4().hex}@example.com"
        db_session = db.session
        db_session.merge(self.user)
        db_session.commit()
        msg = f"User marked as deleted {self.user.id} {self.user.email}"
        logger.info(msg)
        print(msg, file=sys.stderr)
        # self._try_really_delete()

    # def _try_really_delete(self):
    #     try:
    #         db_session = db.session
    #         db_session.delete(self.user)
    #         db_session.commit()
    #     except exc.SQLAlchemyError as e:
    #         # Should be psycopg2.errors.ForeignKeyViolation
    #         # because that user has recodres in BaseContent (publications...)
    #         logger.warning(
    #             f"Impossible to delete user {self.user.id} {self.user.email}"
    #         )
    #         logger.warning(e)

    def _validate_profile_modified(self) -> None:
        # user is a clone of orig user
        orig_user = get_obj(self.user.cloned_user_id, User)
        merge_values_from_other_user(orig_user, self.user)
        auto_organisation = store_user_auto_organisation(orig_user)
        if auto_organisation:
            orig_user.organisation_id = auto_organisation.id
        orig_user.validation_status = LABEL_MODIFICATION_VALIDEE
        orig_user.active = True
        orig_user.validated_at = datetime.now(timezone.utc)

        db_session = db.session
        db_session.merge(orig_user)
        db_session.delete(self.user)
        # db_session.add(user)
        db_session.commit()

    def _validate_profile_created(self) -> None:
        # user is a plain new User
        auto_organisation = store_user_auto_organisation(self.user)
        if auto_organisation:
            self.user.organisation_id = auto_organisation.id
        self.user.active = True
        self.user.validation_status = LABEL_INSCRIPTION_VALIDEE
        self.user.validated_at = now(LOCAL_TZ)
        db_session = db.session
        db_session.merge(self.user)
        db_session.commit()


@blueprint.route("/validation_profile/<uid>")
def validation_profile(uid: str):
    member = ValidationUser(uid)
    return member.render()
