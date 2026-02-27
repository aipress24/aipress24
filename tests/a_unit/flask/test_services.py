# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import TYPE_CHECKING

from svcs.flask import container

from app.services.activity_stream import ActivityStream
from app.services.screenshots import ScreenshotService

if TYPE_CHECKING:
    from flask import Flask


def test_services(app: Flask) -> None:
    activity = container.get(ActivityStream)
    assert activity is not None

    screenshot = container.get(ScreenshotService)
    assert screenshot is not None
