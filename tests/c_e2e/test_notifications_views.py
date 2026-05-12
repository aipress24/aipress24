# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests for the notifications views — regression for bug #0140.

Clicking a notification whose stored URL was a fragment-only value
(`#TODO`) used to cause a 405 because `redirect('#TODO')` re-issued
a GET on the POST-only mark_read route. We now reject fragment-only
URLs in `_is_safe_url` and fall back to the home page.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select
from svcs.flask import container

from app.flask.extensions import db
from app.models.auth import User
from app.services.notifications import NotificationService

if TYPE_CHECKING:
    from flask.testing import FlaskClient


def _get_test_user() -> User:
    return db.session.execute(
        select(User).where(User.email == "test@example.com")
    ).scalar_one()


def _post_a_notification(user: User, url: str) -> int:
    service = container.get(NotificationService)
    notif = service.post(user, "test", url=url)
    db.session.commit()
    return notif.id


def test_mark_read_with_fragment_only_url_does_not_405(
    logged_in_client: FlaskClient,
) -> None:
    """Regression for #0140.

    A notification stored with a fragment-only URL (`#TODO`, `#foo`)
    must not redirect to a fragment that the browser resolves back
    onto the POST-only route.
    """
    user = _get_test_user()
    notif_id = _post_a_notification(user, "#TODO")

    response = logged_in_client.post(
        f"/notifications/{notif_id}/read",
        data={"url": "#TODO"},
    )
    assert response.status_code == 302
    location = response.headers.get("Location", "")
    assert "#TODO" not in location
    assert f"/notifications/{notif_id}/read" not in location


def test_mark_read_with_valid_url_redirects(
    logged_in_client: FlaskClient,
) -> None:
    """Sanity check: a valid same-origin URL is honored."""
    user = _get_test_user()
    notif_id = _post_a_notification(user, "/wip/opportunities")

    response = logged_in_client.post(
        f"/notifications/{notif_id}/read",
        data={"url": "/wip/opportunities"},
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/wip/opportunities")
