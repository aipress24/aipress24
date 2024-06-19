# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.flask.routing import url_for
from app.models.content.events import Event


@url_for.register
def url_for_event(event: Event, _ns: str = "events", **kw):
    name = f"{_ns}.event"
    kw["id"] = event.id
    # if _ns == "public":
    #     kw["slug"] = event.slug

    return url_for(name, **kw)
