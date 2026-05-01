# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""BW Stage B6 — `/BW/assign-missions` permissions assignment.

Drives ``app.modules.bw.bw_activation.routes.stage_b6`` (56 stmts à
~54% pre-push). Le route est le dernier step du tunnel BW : assigner
des permissions aux PR Managers sur le BW.

Routes couvertes :
- GET /BW/assign-missions → renders form pre-rempli depuis session.
- POST /BW/assign-missions avec différentes combinaisons de
  missions cochées + ``action`` ∈ {previous, finish, unknown}.

Le `case _: raise ValueError(msg)` est testé via un POST avec
action invalide (asserte le 500 — c'est un bug défensif côté code,
qui pourrait être refactor en flash + redirect).
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

# Erick's media BW (réutilisé par les tests bw lifecycle).
_ERICK_BW_ID = "3be67123-b68d-48ad-9043-e2a206d18893"


def _setup_erick_bw_session(
    page: Page, base_url: str, profile, login, authed_post
) -> bool:
    """Login PRESS_MEDIA + select erick's BW. Returns True if
    /BW/assign-missions is reachable (BW activated, manager role)."""
    p = profile("PRESS_MEDIA")
    login(p)
    sel = authed_post(
        f"{base_url}/BW/select-bw/{_ERICK_BW_ID}", {}
    )
    if sel["status"] >= 400 or "/auth/login" in sel["url"]:
        return False
    return True


def test_assign_missions_get_renders(
    page: Page, base_url: str, profile, login, authed_post
) -> None:
    """``GET /BW/assign-missions`` rend le form post-fill_session."""
    if not _setup_erick_bw_session(
        page, base_url, profile, login, authed_post
    ):
        pytest.skip("can't setup erick BW session")
    resp = page.goto(
        f"{base_url}/BW/assign-missions",
        wait_until="domcontentloaded",
    )
    assert resp is not None and resp.status < 400, (
        f"/BW/assign-missions GET : "
        f"status={resp.status if resp else '?'}"
    )
    body = page.content()
    assert "Internal Server Error" not in body
    # Form has at least one mission_* checkbox.
    has_missions_inputs = page.locator(
        'input[name^="mission_"]'
    ).count()
    assert has_missions_inputs >= 1, (
        "/BW/assign-missions : no mission_* inputs rendered — "
        "form structure may have changed"
    )


@pytest.mark.mutates_db
@pytest.mark.parametrize(
    ("missions_payload", "label"),
    [
        ({}, "all-off"),
        (
            {
                "mission_press_release": "on",
                "mission_events": "on",
            },
            "press-events",
        ),
        (
            {
                "mission_press_release": "on",
                "mission_events": "on",
                "mission_missions": "on",
                "mission_projects": "on",
                "mission_internships": "on",
                "mission_apprenticeships": "on",
                "mission_doctoral": "on",
            },
            "all-on",
        ),
    ],
    ids=lambda v: v if isinstance(v, str) else None,
)
def test_assign_missions_post_finish_action(
    page: Page,
    base_url: str,
    profile,
    login,
    authed_post,
    missions_payload: dict,
    label: str,
) -> None:
    """``POST /BW/assign-missions`` avec ``action=finish`` →
    persist missions dict + redirect dashboard.

    Drives la construction du missions dict (7 PermissionType
    flags) + sync_all_pr_missions + db.commit. Les 3 paramétrages
    couvrent : aucune mission, sous-ensemble, toutes les missions.
    """
    if not _setup_erick_bw_session(
        page, base_url, profile, login, authed_post
    ):
        pytest.skip("can't setup erick BW session")

    page.goto(
        f"{base_url}/BW/assign-missions",
        wait_until="domcontentloaded",
    )
    payload = {**missions_payload, "action": "finish"}
    resp = authed_post(
        f"{base_url}/BW/assign-missions", payload
    )
    assert resp["status"] < 400, f"assign-missions {label} : {resp}"
    assert "/auth/login" not in resp["url"]
    # `case "finish"` → redirect to dashboard.
    assert "/BW/dashboard" in resp["url"], (
        f"finish action : expected /BW/dashboard, got {resp['url']}"
    )


@pytest.mark.mutates_db
def test_assign_missions_post_previous_action(
    page: Page, base_url: str, profile, login, authed_post
) -> None:
    """``POST /BW/assign-missions`` avec ``action=previous`` :
    pour un media BW, redirige vers manage_external_partners.
    Drives le `case "previous"` branche `bw_type != "pr"`."""
    if not _setup_erick_bw_session(
        page, base_url, profile, login, authed_post
    ):
        pytest.skip("can't setup erick BW session")
    page.goto(
        f"{base_url}/BW/assign-missions",
        wait_until="domcontentloaded",
    )
    resp = authed_post(
        f"{base_url}/BW/assign-missions",
        {"action": "previous"},
    )
    assert resp["status"] < 400, f"assign-missions previous : {resp}"
    # bw_type = media → redirect to manage_external_partners.
    assert "/BW/manage-external-partners" in resp["url"], (
        f"previous action (media) : expected manage-external-partners, "
        f"got {resp['url']}"
    )


@pytest.mark.mutates_db
def test_assign_missions_post_unknown_action_500(
    page: Page, base_url: str, profile, login, authed_post
) -> None:
    """``POST /BW/assign-missions`` avec une action inconnue : le
    `case _:` lève `ValueError`, Werkzeug remonte en 500.

    Pin du comportement actuel — défensif mais probablement fragile
    (un raise ValueError pour un mauvais form input devrait être un
    400 ou un flash + redirect).
    """
    if not _setup_erick_bw_session(
        page, base_url, profile, login, authed_post
    ):
        pytest.skip("can't setup erick BW session")
    page.goto(
        f"{base_url}/BW/assign-missions",
        wait_until="domcontentloaded",
    )
    resp = authed_post(
        f"{base_url}/BW/assign-missions",
        {"action": "no_such_action"},
    )
    # Pin current behavior : ValueError → 500.
    assert resp["status"] == 500, (
        f"unknown action : expected 500 (ValueError uncaught), got "
        f"{resp['status']}"
    )
