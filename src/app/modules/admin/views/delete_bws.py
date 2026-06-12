# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin view to delete all Business Walls."""

from __future__ import annotations

from flask import flash, redirect, render_template, request, url_for
from sqlalchemy import update

from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.admin import blueprint
from app.modules.bw.bw_activation.models import BusinessWall


def _remove_all_bw() -> int:
    """Remove all Business Walls and clear related user/org fields.

    Returns the number of BusinessWall records deleted.
    """
    bw_count = db.session.query(BusinessWall).count()
    if bw_count == 0:
        return 0

    # 1. Clear selected_bw_id for all users
    db.session.execute(update(User).values(selected_bw_id=None))

    # 2. Clear BW-related fields on all organisations
    db.session.execute(
        update(Organisation).values(
            bw_id=None,
            bw_active=None,
            bw_name="",
        )
    )

    # 3. Delete all BusinessWall records (cascade handles associated data)
    db.session.query(BusinessWall).delete()

    db.session.commit()
    return bw_count


@blueprint.route("/delete-bws", methods=["GET", "POST"])
@nav(parent="index", icon="trash-2", label="Delete BWs")
def delete_bws():
    """Confirmation page for deletion."""
    bw_count = db.session.query(BusinessWall).count()

    if request.method == "POST":
        deleted = _remove_all_bw()
        if deleted:
            flash(
                f"{deleted} Business Wall(s) and associated data have been deleted.",
                "success",
            )
        else:
            flash("No Business Wall records found. Nothing to delete.", "info")
        return redirect(url_for("admin.dashboard"))

    return render_template(
        "admin/pages/delete_bws.j2",
        title="Delete Business Walls",
        bw_count=bw_count,
    )
