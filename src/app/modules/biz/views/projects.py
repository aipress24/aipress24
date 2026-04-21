# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Marketplace — Projects (editorial projects) views."""

from __future__ import annotations

from typing import cast

from flask import flash, g, redirect, render_template, request, url_for
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
from app.modules.biz import blueprint
from app.modules.biz.models import (
    ApplicationStatus,
    MissionStatus,
    ProjectOffer,
)
from app.modules.biz.views._offers_common import (
    date_to_datetime,
    default_new_offer_status,
    euros_to_cents,
    get_offer_or_404,
    get_user_application,
    handle_apply,
    list_applications,
    mark_filled,
    require_owner,
    update_application_status,
)


class ProjectOfferForm(Form):
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
    budget_min = IntegerField("Budget min (€)", validators=[validators.Optional()])
    budget_max = IntegerField("Budget max (€)", validators=[validators.Optional()])
    deadline = DateField("Date limite", validators=[validators.Optional()])
    team_size = IntegerField(
        "Taille d'équipe recherchée",
        validators=[validators.Optional(), validators.NumberRange(min=1)],
    )
    duration_months = IntegerField(
        "Durée (mois)",
        validators=[validators.Optional(), validators.NumberRange(min=1)],
    )
    project_type = StringField(
        "Type de projet (dossier, série, enquête...)",
        validators=[validators.Optional()],
    )
    contact_email = StringField(
        "E-mail de contact (optionnel)",
        validators=[validators.Optional(), validators.Email()],
    )


@blueprint.route("/projects/new", methods=["GET", "POST"])
def projects_new():
    user = cast(User, g.user)

    form = ProjectOfferForm(request.form)
    if request.method == "POST" and form.validate():
        project = ProjectOffer(
            title=form.title.data or "",
            description=form.description.data or "",
            sector=form.sector.data or "",
            location=form.location.data or "",
            budget_min=euros_to_cents(form.budget_min.data),
            budget_max=euros_to_cents(form.budget_max.data),
            deadline=date_to_datetime(form.deadline.data),
            team_size=form.team_size.data,
            duration_months=form.duration_months.data,
            project_type=form.project_type.data or "",
            contact_email=form.contact_email.data or "",
            status=default_new_offer_status(),
            mission_status=MissionStatus.OPEN,
            owner_id=user.id,
            emitter_org_id=getattr(user, "organisation_id", None),
        )
        db.session.add(project)
        db.session.commit()
        msg = (
            "Projet envoyé pour modération."
            if project.status.value == "pending"
            else "Projet publié."
        )
        flash(msg, "success")
        return redirect(url_for(".projects_detail", id=project.id))

    return render_template(
        "pages/projects/new.j2", form=form, title="Publier un projet"
    )


@blueprint.route("/projects/<int:id>")
def projects_detail(id: int):
    project = get_offer_or_404(ProjectOffer, id)
    user = cast(User, g.user)

    user_application = None
    if not user.is_anonymous and user.id != project.owner_id:
        user_application = get_user_application(project.id, user)

    return render_template(
        "pages/projects/detail.j2",
        project=project,
        user_application=user_application,
        is_owner=(not user.is_anonymous and user.id == project.owner_id),
        title=project.title,
    )


@blueprint.route("/projects/<int:id>/apply", methods=["POST"])
def projects_apply(id: int):
    project = get_offer_or_404(ProjectOffer, id)
    return handle_apply(project, detail_endpoint=".projects_detail")


@blueprint.route("/projects/<int:id>/applications")
def projects_applications(id: int):
    project = get_offer_or_404(ProjectOffer, id)
    require_owner(project)
    return render_template(
        "pages/projects/applications.j2",
        project=project,
        applications=list_applications(project),
        title=f"Candidatures — {project.title}",
    )


@blueprint.route(
    "/projects/<int:id>/applications/<int:app_id>/select", methods=["POST"]
)
def projects_application_select(id: int, app_id: int):
    project = get_offer_or_404(ProjectOffer, id)
    return update_application_status(
        project, app_id, ApplicationStatus.SELECTED, ".projects_applications"
    )


@blueprint.route(
    "/projects/<int:id>/applications/<int:app_id>/reject", methods=["POST"]
)
def projects_application_reject(id: int, app_id: int):
    project = get_offer_or_404(ProjectOffer, id)
    return update_application_status(
        project, app_id, ApplicationStatus.REJECTED, ".projects_applications"
    )


@blueprint.route("/projects/<int:id>/fill", methods=["POST"])
def projects_fill(id: int):
    project = get_offer_or_404(ProjectOffer, id)
    return mark_filled(project, ".projects_detail")
