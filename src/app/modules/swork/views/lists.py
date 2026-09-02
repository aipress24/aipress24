# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""The four directory landing pages.

Each was its own 22-line module exporting one 6-line function; they
differed by a route, an icon, a title and a template (audit 2026-09-02).
Still four explicit handlers rather than a registration loop — a route
you can grep for beats four lines saved.
"""

from __future__ import annotations

from flask import render_template

from app.flask.lib.nav import nav
from app.modules.swork import blueprint


@blueprint.route("/members/")
@nav(parent="swork", icon="users")
def members():
    """Membres"""
    return render_template("pages/members.j2", title="Membres")


@blueprint.route("/organisations/")
@nav(parent="swork", icon="building-office")
def organisations():
    """Organisations"""
    return render_template("pages/orgs.j2", title="Organisations")


@blueprint.route("/groups/")
@nav(parent="swork", icon="user-group")
def groups():
    """Groupes"""
    return render_template("pages/groups.j2", title="Groupes")


@blueprint.route("/parrainages/")
@nav(parent="swork", icon="heart")
def parrainages():
    """Parrainages"""
    return render_template("pages/members.j2", title="Parrainages")
