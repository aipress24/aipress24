# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import sys
from datetime import datetime, timezone

from flask import Response, g, request
from loguru import logger
from sqlalchemy import exc

from app.flask.extensions import db
from app.flask.lib.pages import page
from app.flask.sqla import get_obj
from app.models.auth import User, merge_values_from_other_user
from app.modules.kyc.organisation_utils import store_light_organisation
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

    def context(self):
        context = admin_info_context(self.user)
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
        if self.user.email_backup:
            self._validate_profile_modified()
        else:
            self._validate_profile_created()
        self._store_organisation_name()

    def _store_organisation_name(self) -> None:
        """Remember the organisation name in list of organisation
        (media, rp, instit, autre)"""
        profile = self.user.profile
        orga_field_name = profile.organisation_field_name_origin
        current_value = profile.get_value(orga_field_name)
        if isinstance(current_value, list):  # newsroom is a list
            if current_value:
                name = current_value[0]
            else:
                name = ""
        else:
            name = current_value
        name = name.strip()
        if not name:
            return
        family = profile.organisation_family  # select the target family
        store_light_organisation(name, family)

    def _reject_profile(self) -> None:
        # shoud not be a clone: a plain new user (creation)
        self.user.deleted = True
        self.user.active = False
        # we need to free the rejectd user email because
        # it's a 'unique' field'
        self.user.email = f"fake_{self.user.id}@example.com"
        db_session = db.session
        db_session.merge(self.user)
        db_session.commit()
        msg = f"User marked as deleted {self.user.id} {self.user.email}"
        logger.info(msg)
        print(msg, file=sys.stderr)
        # self._try_really_delete()

    def _try_really_delete(self):
        try:
            db_session = db.session
            db_session.delete(self.user)
            db_session.commit()
        except exc.SQLAlchemyError as e:
            # Should be psycopg2.errors.ForeignKeyViolation
            # because that user has recodres in BaseContent (publications...)
            logger.warning(
                f"Impossible to delete user {self.user.id} {self.user.email}"
            )
            logger.warning(e)

    def _validate_profile_modified(self) -> None:
        # user is a clone of orig user
        orig_user = get_obj(self.user.cloned_user_id, User)
        merge_values_from_other_user(orig_user, self.user)
        orig_user.user_valid_comment = "Modifications validées"
        orig_user.active = True
        orig_user.user_date_valid = datetime.now(timezone.utc)

        db_session = db.session
        db_session.merge(orig_user)
        db_session.delete(self.user)
        # db_session.add(user)
        db_session.commit()

    def _validate_profile_created(self) -> None:
        # user is a plain new User
        self.user.active = True
        self.user.user_valid_comment = "Nouvel utilisateur validé"
        self.user.user_date_valid = datetime.now(timezone.utc)

        db_session = db.session
        db_session.merge(self.user)
        db_session.commit()


@blueprint.route("/validation_profile/<uid>")
def validation_profile(uid: str):
    member = ValidationUser(uid)
    return member.render()
