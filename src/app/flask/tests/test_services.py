# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import Flask
from svcs.flask import container

from app.services.activity_stream import ActivityStream
from app.services.screenshots import ScreenshotService


def test_services(app: Flask):
    activity = container.get(ActivityStream)
    assert activity is not None

    screenshot = container.get(ScreenshotService)
    assert screenshot is not None
