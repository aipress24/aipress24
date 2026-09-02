# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""The WIRE blueprint is closed to visitors — sentinel, 2026-09-02.

`app/modules/wire/__init__.py` raises `Unauthorized` in its
`before_request`. Four purchase views repeated that check, and a fifth —
`_get_purchase_or_404` — had it backwards: it *exempted* anonymous
callers from the ownership check instead of refusing them. The four
duplicates are gone and the inverted condition is fixed, which leaves
`before_request` solely in charge.

This file is the sentinel that goes with that: if the guard disappears,
it is no longer a redundancy that goes but access that opens — on
`/wire/purchase/<id>/success`, whose ids are sequential integers.
"""

from __future__ import annotations

import pytest
from flask import Flask

# One URL per shape of view: list, purchase detail, price modal, buy
# POST. All must send a visitor to the home page or to login, never to a
# page body.
URLS_GET = [
    "/wire/",
    "/wire/purchase/1/success",
    "/wire/purchase/1/cancel",
    "/wire/1/buy_modal/consultation",
    "/wire/1/buy_modal_gift",
]
URLS_POST = [
    "/wire/1/buy/consultation",
    "/wire/1/buy_gift",
]


@pytest.mark.parametrize("url", URLS_GET)
def test_a_visitor_reaches_no_wire_view(client, url) -> None:
    response = client.get(url)

    assert response.status_code in (301, 302, 401), (
        f"{url} answered {response.status_code} to an anonymous caller"
    )


@pytest.mark.parametrize("url", URLS_POST)
def test_nor_through_a_post(client, url) -> None:
    response = client.post(url, data={})

    assert response.status_code in (301, 302, 401), (
        f"{url} answered {response.status_code} to an anonymous caller"
    )


def test_the_guard_lives_in_the_before_request(app: Flask) -> None:
    """The tests above would also pass if every view guarded itself.

    What we want to assert is that the guard is **single and central**:
    it is what allows the views to treat `g.user` as a signed-in member.
    """
    assert app.before_request_funcs.get("wire"), (
        "the WIRE blueprint no longer registers a before_request"
    )
