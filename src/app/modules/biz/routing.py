# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.flask.routing import url_for

from .models import MarketplaceContent


@url_for.register
def url_for_biz_item(obj: MarketplaceContent, _ns: str = "biz", **kw):
    name = f"{_ns}.biz_item"
    kw["id"] = obj.id
    return url_for(name, **kw)
