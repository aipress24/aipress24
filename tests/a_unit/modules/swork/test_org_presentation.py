# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit test for Organisation presentation in A propos tab."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from flask import Flask

from app.models.organisation import Organisation
from app.modules.swork.views.organisation import OrgVM


def test_org_vm_presentation_returns_bw_presentation() -> None:
    org = Organisation(name="Test Org")
    vm = OrgVM(org)

    # no BW: presentation is empty
    vm._cached_bw = None
    assert vm.presentation == ""

    # BW has presentation;: content
    mock_bw = MagicMock()
    mock_bw.id = uuid.uuid4()
    mock_bw.presentation = "Notre présentation officielle."
    vm._cached_bw = mock_bw
    assert vm.presentation == "Notre présentation officielle."


def test_org_profile_tab_template_renders_presentation(app: Flask) -> None:
    org = Organisation(name="Test Org")
    vm = OrgVM(org)
    mock_bw = MagicMock()
    mock_bw.id = uuid.uuid4()
    mock_bw.presentation = "Voici la présentation de l'organisation."
    mock_bw.owner_id = None
    vm._cached_bw = mock_bw

    with app.test_request_context():
        res = app.jinja_env.get_template("pages/org/org--tab-profile.j2").render(
            org=vm,
            tab="profile",
            line=lambda label, val: f"{label}: {val}",
        )
        assert ">Présentation<" in res
        assert (
            "Voici la présentation de l&#39;organisation." in res
            or "Voici la présentation de l'organisation." in res
        )


def test_org_profile_tab_template_omits_presentation_when_empty(app: Flask) -> None:
    org = Organisation(name="Test Org")
    vm = OrgVM(org)
    mock_bw = MagicMock()
    mock_bw.id = uuid.uuid4()
    mock_bw.presentation = ""
    mock_bw.owner_id = None
    vm._cached_bw = mock_bw

    with app.test_request_context():
        res = app.jinja_env.get_template("pages/org/org--tab-profile.j2").render(
            org=vm,
            tab="profile",
            line=lambda label, val: f"{label}: {val}",
        )
        assert "Présentation" not in res
