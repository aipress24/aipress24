# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""The livewire route is a public URL taking client-written component state."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from app.models.auth import User

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session
    from werkzeug.test import TestResponse

URL = "/livewire/message/members-list"
MEMBER_NAME = "Zephyrine"


def _message(
    data: dict[str, Any] | None = None, updates: list[dict] | None = None
) -> dict[str, Any]:
    return {
        "fingerprint": {"id": "component-id"},
        "serverMemo": {"data": {"search": "", "filter_states": {}, **(data or {})}},
        "updates": updates or [],
    }


def _call(method: str, *params: Any) -> dict[str, Any]:
    return {"type": "callMethod", "payload": {"method": method, "params": list(params)}}


def _sync(name: str, value: Any) -> dict[str, Any]:
    return {"type": "syncInput", "payload": {"name": name, "value": value}}


def _json_body(response: TestResponse) -> dict[str, Any]:
    body = response.get_json()
    assert isinstance(body, dict)
    return body


@pytest.fixture
def member(db_session: Session) -> User:
    user = User(email="zephyrine@example.com", first_name=MEMBER_NAME, last_name="Doe")
    user.photo = b""
    user.active = True
    db_session.add(user)
    db_session.commit()
    return user


def test_anonymous_visitor_gets_no_directory(client: FlaskClient, member: User) -> None:
    response = client.post(URL, json=_message())

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
    assert MEMBER_NAME.encode() not in response.data


def test_member_can_search_the_directory(
    logged_in_client: FlaskClient, member: User
) -> None:
    updates = [_sync("search", MEMBER_NAME), _call("action_apply_filters")]

    response = logged_in_client.post(URL, json=_message(updates=updates))

    assert response.status_code == 200
    body = _json_body(response)
    assert MEMBER_NAME in body["effects"]["html"]
    assert body["serverMemo"]["data"]["search"] == MEMBER_NAME


def test_member_can_untick_a_filter(
    logged_in_client: FlaskClient, member: User
) -> None:
    updates = [_sync("filter_states.job_title.0", False), _call("action_apply_filters")]
    data = {"filter_states": {"job_title": {"0": True}}}

    response = logged_in_client.post(URL, json=_message(data, updates))

    assert response.status_code == 200
    states = _json_body(response)["serverMemo"]["data"]["filter_states"]
    assert states["job_title"]["0"] is False


@pytest.mark.parametrize(
    "message",
    [
        pytest.param(_message(data={"_template": "{self._id}"}), id="restored-state"),
        pytest.param(
            _message(updates=[_sync("_template", "{self._id}")]), id="synced-input"
        ),
        pytest.param(
            _message(updates=[_call("__setattr__", "_template", "{self._id}")]),
            id="dunder-call",
        ),
        pytest.param(
            _message(updates=[_call("_restore", {"_template": "{self._id}"})]),
            id="private-call",
        ),
        pytest.param(_message(updates=[_call("render")]), id="non-action-call"),
    ],
)
def test_client_cannot_reach_beyond_declared_state_and_actions(
    logged_in_client: FlaskClient, message: dict[str, Any]
) -> None:
    response = logged_in_client.post(URL, json=message)

    assert response.status_code == 400
    assert b"component-id" not in response.data
