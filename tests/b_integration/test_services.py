# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

from flask_super.registry import lookup
from svcs.flask import container


def test_services(app_context) -> None:
    for service_class in lookup(tag="service"):
        service = container.get(service_class)
        assert isinstance(service, service_class)
