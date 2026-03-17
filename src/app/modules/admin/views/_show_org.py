# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Show org helpers for admin views."""

from __future__ import annotations

from typing import cast

from attr import define
from flask import current_app
from sqlalchemy.exc import NoInspectionAvailable

from app.flask.lib.view_model import ViewModel
from app.models.organisation import Organisation
from app.modules.admin.invitations import emails_invited_to_organisation
from app.modules.bw.bw_activation.models import BusinessWall
from app.modules.bw.bw_activation.user_utils import (
    get_active_business_wall_for_organisation,
    get_organisation_logo_url,
)


@define
class OrgVM(ViewModel):
    @property
    def org(self):
        return cast("Organisation", self._model)

    def extra_attrs(self):
        members = self.get_members()
        active_bw = self.get_active_business_wall()
        return {
            "members": members,
            "count_members": len(self.org.members),
            "managers": self.org.managers,
            "leaders": self.org.leaders,
            "invitations_emails": emails_invited_to_organisation(self.org.id),
            "logo_url": self.get_logo_url(),
            "screenshot_url": self.get_screenshot_url(),
            "address_formatted": self.org.formatted_address,
            "active_business_wall": active_bw,
            "has_active_bw": active_bw is not None,
        }

    def get_active_business_wall(self) -> BusinessWall | None:
        """Get the active BusinessWall associated with this organisation."""
        try:
            return get_active_business_wall_for_organisation(self.org)
        except NoInspectionAvailable:
            # Handle case where org is not a SQLAlchemy model (e.g., test stubs)
            return None

    def get_members(self) -> list:
        return list(self.org.members)

    def get_logo_url(self):
        return get_organisation_logo_url(self.org)

    def get_screenshot_url(self):
        if not self.org.screenshot_id:
            return ""
        config = current_app.config
        base_url = config["S3_PUBLIC_URL"]
        url = f"{base_url}/{self.org.screenshot_id}"
        return url
