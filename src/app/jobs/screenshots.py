# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask_super.registry import register
from sqlalchemy import select
from svcs.flask import container

from app.flask.extensions import db
from app.flask.lib.jobs import Job
from app.models.organisation import Organisation
from app.services.screenshots import ScreenshotService
from app.services.web import check_url


@register
class ScreenshotsJob(Job):
    name = "screenshots"
    description = "Take screenshots"

    def run(self, *args) -> None:
        stmt = select(Organisation)
        result = db.session.execute(stmt)
        orgs: list[Organisation] = list(result.scalars())

        for org in orgs:
            self.take_screenshot(org)
            db.session.commit()

    def take_screenshot(self, org: Organisation) -> None:
        url: str = org.site_url
        if not url:
            return

        if not check_url(url):
            return

        screenshot_service = container.get(ScreenshotService)
        session = screenshot_service.start_session(url)
        org.screenshot_id = session.object_id
