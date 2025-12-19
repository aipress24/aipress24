# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Member detail view."""

from __future__ import annotations

import random

from flask import Response, g, make_response, redirect, render_template, request
from sqlalchemy.orm import selectinload

from app.flask.extensions import db, htmx
from app.flask.lib.nav import nav
from app.flask.lib.toaster import toast
from app.flask.routing import url_for
from app.flask.sqla import get_obj
from app.models.auth import User
from app.modules.swork import blueprint
from app.modules.swork.views._common import MEMBER_TABS, UserVM, filter_email_mobile


@blueprint.route("/members/<id>")
@nav(parent="members")
def member(id: str):
    """Membre"""
    options = selectinload(User.organisation)
    user = get_obj(id, User, options=options)

    # Set dynamic breadcrumb label
    g.nav.label = f"{user.last_name}, {user.first_name}"

    active_tab = request.args.get("tab", "profile")

    # Handle HTMX tab requests
    if htmx:
        return _render_tab(user, active_tab)

    return _render_full_page(user, active_tab)


def _render_full_page(user: User, active_tab: str) -> str:
    """Render full member page."""
    ctx = _build_context(user, active_tab)
    ctx["title"] = f"{user.last_name}, {user.first_name}"
    return render_template("pages/member.j2", **ctx)


def _render_tab(user: User, active_tab: str) -> str:
    """Render just a tab fragment for HTMX requests."""
    ctx = _build_context(user, active_tab)
    template_map = {
        "profile": "pages/member/member--tab-profile.j2",
        "publications": "pages/member/member--tab-publications.j2",
        "activities": "pages/member/member--tab-activities.j2",
        "groups": "pages/member/member--tab-groups.j2",
        "followers": "pages/member/member--tab-followers.j2",
        "followees": "pages/member/member--tab-followees.j2",
    }
    template = template_map.get(active_tab, "pages/member/member--tab-profile.j2")
    return render_template(template, **ctx)


def _build_context(user: User, active_tab: str) -> dict:
    """Build context for member page."""
    # Lazy import to avoid circular import
    from app.modules.kyc.views import public_info_context

    user_vm = UserVM(user)

    followers = user_vm.followers
    if len(followers) > 5:
        followers_sample = random.sample(followers, 5)
    else:
        followers_sample = followers

    mask_fields = filter_email_mobile(g.user, user)
    context = public_info_context(user, mask_fields)
    context.update(
        {
            "profile": user_vm,
            "tabs": MEMBER_TABS,
            "active_tab": active_tab,
            "followers_sample": followers_sample,
        }
    )
    return context


@blueprint.route("/members/<id>", methods=["POST"])
@nav(hidden=True)
def member_post(id: str) -> Response | str:
    """Handle POST actions on member (follow/unfollow)."""
    options = selectinload(User.organisation)
    user = get_obj(id, User, options=options)
    action = request.form.get("action", "")

    match action:
        case "toggle-follow":
            return _toggle_follow(user)
        case _:
            return ""


def _toggle_follow(user: User) -> Response:
    """Toggle follow status for a user."""
    from app.services.social_graph import SocialUser, adapt

    logged_user: SocialUser = adapt(g.user)

    if logged_user.is_following(user):
        logged_user.unfollow(user)
        response = make_response("Suivre")
        toast(response, f"Vous ne suivez plus {user.full_name}")
    else:
        logged_user.follow(user)
        response = make_response("Ne plus suivre")
        toast(response, f"Vous suivez a présent {user.full_name}")

    db.session.commit()
    return response


@blueprint.route("/profile/")
@nav(hidden=True)
def profile():
    """Redirect to logged user's member page."""
    logged_user = g.user
    return redirect(url_for(logged_user))
