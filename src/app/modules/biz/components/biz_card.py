# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from attr import frozen

from app.flask.lib.pywire import Component, component
from app.modules.biz.models import MarketplaceContent


@component
@frozen
class BizCard(Component):
    obj: MarketplaceContent
    show_author: bool = True
