# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Bug 0133: the "Médias" picker offered to journalists when they propose a
sujet (or article / avis d'enquête / commande) must list ONLY organisations
with an active "Business Wall for Media" subscription.

Before this fix the query also pulled in organisations with `bw_id IS NULL`
(auto-created placeholder orgs), so the dropdown drowned the real media in
junk. The fix tightens `BaseWipView.get_media_organisations` to a strict
`bw_id IS NOT NULL AND bw_active == "media"` filter.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from flask import g

from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.wip.crud.cbvs._base import BaseWipView

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


@pytest.fixture
def picker_user(db_session: Session) -> User:
    user = User(email="picker-user@example.com", first_name="P", last_name="U")
    user.photo = b""
    user.active = True
    db_session.add(user)
    db_session.flush()
    return user


def _make_org(
    db_session: Session,
    *,
    name: str,
    has_bw: bool,
    bw_active: str,
) -> Organisation:
    org = Organisation(name=name)
    if has_bw:
        org.bw_id = uuid.uuid4()
        org.bw_active = bw_active
        org.bw_name = name
    db_session.add(org)
    db_session.flush()
    return org


class _ConcreteView(BaseWipView):
    """BaseWipView is abstract; we only need it to invoke
    `get_media_organisations`, so we provide a minimal concrete subclass.
    `get_media_organisations` does not look at any of these attributes."""

    name = "test"
    model_class = Organisation
    form_class = type("F", (), {})  # type: ignore[assignment]
    repo_class = type("R", (), {})  # type: ignore[assignment]
    table_class = type("T", (), {})  # type: ignore[assignment]
    doc_type = "test"

    label_main = ""
    label_list = ""
    label_new = ""
    label_edit = ""
    label_view = ""
    icon = ""
    msg_delete_ok = ""
    msg_delete_ko = ""
    table_id = "test"


class TestGetMediaOrganisationsScope:
    """Bug 0133: only organisations with an ACTIVE media BW must appear."""

    def test_includes_org_with_active_media_bw(
        self,
        app: Flask,
        db_session: Session,
        picker_user: User,
    ):
        media = _make_org(db_session, name="Real Media", has_bw=True, bw_active="media")

        with app.test_request_context():
            g.user = picker_user
            choices = _ConcreteView().get_media_organisations()

        assert (str(media.id), media.name) in choices

    def test_excludes_auto_org_with_no_bw(
        self,
        app: Flask,
        db_session: Session,
        picker_user: User,
    ):
        auto = _make_org(db_session, name="Auto Junk", has_bw=False, bw_active="")

        with app.test_request_context():
            g.user = picker_user
            choices = _ConcreteView().get_media_organisations()

        ids = [c[0] for c in choices]
        assert str(auto.id) not in ids, (
            "auto-created placeholder orgs must not appear in the media picker"
        )

    def test_excludes_org_with_non_media_bw(
        self,
        app: Flask,
        db_session: Session,
        picker_user: User,
    ):
        # PR agency has bw_id but bw_active="pr" — must not appear in MEDIA picker.
        pr = _make_org(db_session, name="PR Agency", has_bw=True, bw_active="pr")

        with app.test_request_context():
            g.user = picker_user
            choices = _ConcreteView().get_media_organisations()

        ids = [c[0] for c in choices]
        assert str(pr.id) not in ids

    def test_user_own_org_prepended_when_set(
        self,
        app: Flask,
        db_session: Session,
        picker_user: User,
    ):
        # Existing behaviour: the user's own org gets prepended (under bw_name)
        # even if it isn't a media BW. The fix must NOT regress that.
        own = _make_org(db_session, name="My Own Org", has_bw=True, bw_active="pr")
        own.bw_name = "MY OWN BW"
        picker_user.organisation_id = own.id
        db_session.flush()

        with app.test_request_context():
            g.user = picker_user
            choices = _ConcreteView().get_media_organisations()

        # First entry is the user's own org with its bw_name as the label.
        assert choices[0] == (str(own.id), "MY OWN BW")
