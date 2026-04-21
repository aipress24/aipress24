# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Marketplace — Missions MVP views.

- GET /biz/missions/new           — form to post a new mission
- POST /biz/missions/new          — submission
- GET /biz/missions/<id>          — public detail page
- POST /biz/missions/<id>/apply   — candidacy submission
- GET /biz/missions/<id>/applications — emitter dashboard
- POST /biz/missions/<id>/applications/<app_id>/select|reject — decisions
- POST /biz/missions/<id>/fill    — mark as filled
"""

from __future__ import annotations

from datetime import datetime
from typing import cast

from flask import (
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)
from wtforms import (
    DateField,
    Form,
    IntegerField,
    StringField,
    TextAreaField,
    validators,
)

from app.flask.extensions import db
from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.modules.biz import blueprint
from app.modules.biz.models import (
    ApplicationStatus,
    MissionApplication,
    MissionOffer,
    MissionStatus,
)
from app.modules.biz.services.mission_notifications import (
    notify_emitter_of_application,
)


class MissionOfferForm(Form):
    title = StringField(
        "Titre",
        validators=[validators.InputRequired(), validators.Length(max=200)],
    )
    description = TextAreaField(
        "Description",
        validators=[validators.InputRequired(), validators.Length(min=20)],
    )
    sector = StringField("Secteur", validators=[validators.Optional()])
    location = StringField("Localisation", validators=[validators.Optional()])
    budget_min = IntegerField(
        "Budget min (€)", validators=[validators.Optional()]
    )
    budget_max = IntegerField(
        "Budget max (€)", validators=[validators.Optional()]
    )
    deadline = DateField("Date limite", validators=[validators.Optional()])
    contact_email = StringField(
        "E-mail de contact (optionnel)",
        validators=[validators.Optional(), validators.Email()],
    )


@blueprint.route("/missions/new", methods=["GET", "POST"])
def missions_new():
    user = cast(User, g.user)

    form = MissionOfferForm(request.form)
    if request.method == "POST" and form.validate():
        mission = MissionOffer(
            title=form.title.data or "",
            description=form.description.data or "",
            sector=form.sector.data or "",
            location=form.location.data or "",
            budget_min=_euros_to_cents(form.budget_min.data),
            budget_max=_euros_to_cents(form.budget_max.data),
            deadline=_date_to_datetime(form.deadline.data),
            contact_email=form.contact_email.data or "",
            status=PublicationStatus.PUBLIC,
            mission_status=MissionStatus.OPEN,
            owner_id=user.id,
            emitter_org_id=getattr(user, "organisation_id", None),
        )
        db.session.add(mission)
        db.session.commit()
        flash("Mission publiée.", "success")
        return redirect(url_for(".missions_detail", id=mission.id))

    return render_template(
        "pages/missions/new.j2", form=form, title="Publier une mission"
    )


@blueprint.route("/missions/<int:id>")
def missions_detail(id: int):
    mission = _get_mission_or_404(id)
    user = cast(User, g.user)

    user_application = None
    if not user.is_anonymous and user.id != mission.owner_id:
        user_application = (
            db.session.query(MissionApplication)
            .filter_by(mission_id=mission.id, owner_id=user.id)
            .first()
        )

    return render_template(
        "pages/missions/detail.j2",
        mission=mission,
        user_application=user_application,
        is_owner=(not user.is_anonymous and user.id == mission.owner_id),
        title=mission.title,
    )


@blueprint.route("/missions/<int:id>/apply", methods=["POST"])
def missions_apply(id: int):
    mission = _get_mission_or_404(id)
    user = cast(User, g.user)

    if user.is_anonymous:
        flash("Connexion requise pour candidater.", "error")
        return redirect(url_for("security.login"))

    if user.id == mission.owner_id:
        flash("Vous ne pouvez pas candidater à votre propre mission.", "error")
        return redirect(url_for(".missions_detail", id=mission.id))

    if mission.mission_status != MissionStatus.OPEN:
        flash("Cette mission n'accepte plus de candidatures.", "error")
        return redirect(url_for(".missions_detail", id=mission.id))

    existing = (
        db.session.query(MissionApplication)
        .filter_by(mission_id=mission.id, owner_id=user.id)
        .first()
    )
    if existing is not None:
        flash("Vous avez déjà candidaté à cette mission.", "info")
        return redirect(url_for(".missions_detail", id=mission.id))

    message = (request.form.get("message") or "").strip()
    application = MissionApplication(
        mission_id=mission.id,
        owner_id=user.id,
        message=message,
    )
    db.session.add(application)
    db.session.commit()

    notify_emitter_of_application(mission=mission, application=application)

    flash("Candidature envoyée.", "success")
    return redirect(url_for(".missions_detail", id=mission.id))


@blueprint.route("/missions/<int:id>/applications")
def missions_applications(id: int):
    mission = _get_mission_or_404(id)
    user = cast(User, g.user)

    if user.is_anonymous or user.id != mission.owner_id:
        abort(403)

    applications = (
        db.session.query(MissionApplication)
        .filter_by(mission_id=mission.id)
        .order_by(MissionApplication.created_at.desc())
        .all()
    )
    return render_template(
        "pages/missions/applications.j2",
        mission=mission,
        applications=applications,
        title=f"Candidatures — {mission.title}",
    )


@blueprint.route(
    "/missions/<int:id>/applications/<int:app_id>/select",
    methods=["POST"],
)
def missions_application_select(id: int, app_id: int):
    return _update_application_status(id, app_id, ApplicationStatus.SELECTED)


@blueprint.route(
    "/missions/<int:id>/applications/<int:app_id>/reject",
    methods=["POST"],
)
def missions_application_reject(id: int, app_id: int):
    return _update_application_status(id, app_id, ApplicationStatus.REJECTED)


@blueprint.route("/missions/<int:id>/fill", methods=["POST"])
def missions_fill(id: int):
    mission = _get_mission_or_404(id)
    user = cast(User, g.user)

    if user.is_anonymous or user.id != mission.owner_id:
        abort(403)

    mission.mission_status = MissionStatus.FILLED
    db.session.commit()
    flash("Mission marquée comme pourvue.", "success")
    return redirect(url_for(".missions_detail", id=mission.id))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_mission_or_404(id: int) -> MissionOffer:
    mission = db.session.get(MissionOffer, id)
    if mission is None or mission.status != PublicationStatus.PUBLIC:
        abort(404)
    return mission


def _update_application_status(
    id: int, app_id: int, new_status: ApplicationStatus
):
    mission = _get_mission_or_404(id)
    user = cast(User, g.user)

    if user.is_anonymous or user.id != mission.owner_id:
        abort(403)

    application = db.session.get(MissionApplication, app_id)
    if application is None or application.mission_id != mission.id:
        abort(404)

    application.status = new_status
    db.session.commit()
    flash(f"Candidature {new_status.value}.", "success")
    return redirect(url_for(".missions_applications", id=mission.id))


def _euros_to_cents(value: int | None) -> int | None:
    if value is None:
        return None
    return value * 100


def _date_to_datetime(value) -> datetime | None:
    if value is None:
        return None
    return datetime.combine(value, datetime.min.time())
