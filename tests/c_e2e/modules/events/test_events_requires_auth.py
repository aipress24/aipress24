# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""The EVENTS blueprint is closed to visitors — sentinel, 2026-09-02.

`app/modules/events/__init__.py` raises `Unauthorized` in its
`before_request`. `EventsListView._upcoming_accredited_events` dropped
its own `is_signed_in` check on the strength of that guard and now reads
`g.user.id` unconditionally.

This is the sentinel that goes with it, the twin of
`tests/c_e2e/modules/wire/test_wire_requires_auth.py`: if the guard
disappears, it is no longer a redundancy that goes but a `/events/`
listing that 500s on `AnonymousUser.id` for every visitor.
"""

from __future__ import annotations

import pytest
from flask import Flask

# One URL per shape of view: listing, detail, calendar.
URLS = [
    "/events/",
    "/events/1",
    "/events/calendar",
]


@pytest.mark.parametrize("url", URLS)
def test_a_visitor_reaches_no_events_view(client, url) -> None:
    response = client.get(url)

    assert response.status_code in (301, 302, 401), (
        f"{url} answered {response.status_code} to an anonymous caller"
    )


def test_the_guard_lives_in_the_before_request(app: Flask) -> None:
    """The tests above would also pass if every view guarded itself.

    What we want to assert is that the guard is **single and central**:
    it is what allows the views to treat `g.user` as a signed-in member.
    """
    assert app.before_request_funcs.get("events"), (
        "the EVENTS blueprint no longer registers a before_request"
    )
