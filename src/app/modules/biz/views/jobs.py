# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Marketplace — Job offers views."""

from __future__ import annotations

from typing import cast

from flask import flash, g, redirect, render_template, request, url_for
from wtforms import (
    BooleanField,
    DateField,
    Form,
    IntegerField,
    SelectField,
    StringField,
    TextAreaField,
    validators,
)

from app.flask.extensions import db
from app.models.auth import User
from app.modules.biz import blueprint
from app.modules.biz.models import (
    ApplicationStatus,
    ContractType,
    JobOffer,
    MissionStatus,
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

_CONTRACT_CHOICES = [
    (ContractType.CDI.value, "CDI"),
    (ContractType.CDD.value, "CDD"),
    (ContractType.STAGE.value, "Stage"),
    (ContractType.APPRENTISSAGE.value, "Apprentissage"),
    (ContractType.FREELANCE.value, "Freelance"),
]


class JobOfferForm(Form):
    title = StringField(
        "Intitulé du poste",
        validators=[validators.InputRequired(), validators.Length(max=200)],
    )
    description = TextAreaField(
        "Description",
        validators=[validators.InputRequired(), validators.Length(min=20)],
    )
    sector = StringField("Secteur", validators=[validators.Optional()])
    location = StringField("Localisation", validators=[validators.Optional()])
    contract_type = SelectField(
        "Type de contrat",
        choices=_CONTRACT_CHOICES,
        default=ContractType.CDI.value,
    )
    full_time = BooleanField("Temps plein", default=True)
    remote_ok = BooleanField("Télétravail possible", default=False)
    salary_min = IntegerField(
        "Salaire min (€ brut/an)", validators=[validators.Optional()]
    )
    salary_max = IntegerField(
        "Salaire max (€ brut/an)", validators=[validators.Optional()]
    )
    starting_date = DateField(
        "Date de prise de poste", validators=[validators.Optional()]
    )
    contact_email = StringField(
        "E-mail de contact (optionnel)",
        validators=[validators.Optional(), validators.Email()],
    )


@blueprint.route("/jobs/new", methods=["GET", "POST"])
def jobs_new():
    user = cast(User, g.user)

    form = JobOfferForm(request.form)
    if request.method == "POST" and form.validate():
        job = JobOffer(
            title=form.title.data or "",
            description=form.description.data or "",
            sector=form.sector.data or "",
            location=form.location.data or "",
            contract_type=ContractType(
                form.contract_type.data or ContractType.CDI.value
            ),
            full_time=bool(form.full_time.data),
            remote_ok=bool(form.remote_ok.data),
            salary_min=euros_to_cents(form.salary_min.data),
            salary_max=euros_to_cents(form.salary_max.data),
            starting_date=date_to_datetime(form.starting_date.data),
            contact_email=form.contact_email.data or "",
            status=default_new_offer_status(),
            mission_status=MissionStatus.OPEN,
            owner_id=user.id,
            emitter_org_id=getattr(user, "organisation_id", None),
        )
        db.session.add(job)
        db.session.commit()
        msg = (
            "Offre d'emploi envoyée pour modération."
            if job.status.value == "pending"
            else "Offre d'emploi publiée."
        )
        flash(msg, "success")
        return redirect(url_for(".jobs_detail", id=job.id))

    return render_template(
        "pages/jobs/new.j2", form=form, title="Publier une offre d'emploi"
    )


@blueprint.route("/jobs/<int:id>")
def jobs_detail(id: int):
    job = get_offer_or_404(JobOffer, id)
    user = cast(User, g.user)

    user_application = None
    if not user.is_anonymous and user.id != job.owner_id:
        user_application = get_user_application(job.id, user)

    return render_template(
        "pages/jobs/detail.j2",
        job=job,
        user_application=user_application,
        is_owner=(not user.is_anonymous and user.id == job.owner_id),
        title=job.title,
    )


@blueprint.route("/jobs/<int:id>/apply", methods=["POST"])
def jobs_apply(id: int):
    job = get_offer_or_404(JobOffer, id)
    cv_url = (request.form.get("cv_url") or "").strip()
    return handle_apply(job, detail_endpoint=".jobs_detail", cv_url=cv_url)


@blueprint.route("/jobs/<int:id>/applications")
def jobs_applications(id: int):
    job = get_offer_or_404(JobOffer, id)
    require_owner(job)
    return render_template(
        "pages/jobs/applications.j2",
        job=job,
        applications=list_applications(job),
        title=f"Candidatures — {job.title}",
    )


@blueprint.route("/jobs/<int:id>/applications/<int:app_id>/select", methods=["POST"])
def jobs_application_select(id: int, app_id: int):
    job = get_offer_or_404(JobOffer, id)
    return update_application_status(
        job, app_id, ApplicationStatus.SELECTED, ".jobs_applications"
    )


@blueprint.route("/jobs/<int:id>/applications/<int:app_id>/reject", methods=["POST"])
def jobs_application_reject(id: int, app_id: int):
    job = get_offer_or_404(JobOffer, id)
    return update_application_status(
        job, app_id, ApplicationStatus.REJECTED, ".jobs_applications"
    )


@blueprint.route("/jobs/<int:id>/fill", methods=["POST"])
def jobs_fill(id: int):
    job = get_offer_or_404(JobOffer, id)
    return mark_filled(job, ".jobs_detail")
