# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Marketplace — Job offers views."""

from __future__ import annotations

from typing import cast

from flask import flash, g, redirect, render_template, request, url_for
from werkzeug.exceptions import Forbidden
from wtforms import (
    BooleanField,
    DateField,
    Form,
    IntegerField,
    SelectField,
    SelectMultipleField,
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
from app.modules.bw.bw_activation.models import PermissionType
from app.modules.bw.bw_activation.user_utils import get_selected_business_wall_for_user
from app.modules.kyc.dynform import CountrySelectField
from app.modules.kyc.field_label import strip_taxonomy_prefix
from app.modules.kyc.ontology_loader import get_choices as get_ontology_choices
from app.modules.wip.pr_access import check_mission
from app.signals import marketplace_published

_CONTRACT_CHOICES = [
    (ContractType.CDI.value, "CDI"),
    (ContractType.CDD.value, "CDD"),
    (ContractType.STAGE.value, "Stage"),
    (ContractType.APPRENTISSAGE.value, "Apprentissage"),
    (ContractType.FREELANCE.value, "Freelance"),
    (ContractType.DOCTORAL.value, "Convention doctorale"),
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
    statut = SelectField(
        "Statut",
        choices=[],
        validate_choice=False,
        validators=[validators.InputRequired(message="Veuillez choisir un statut.")],
    )
    domain_studient = SelectField(
        "Domaine d'application",
        choices=[],
        validate_choice=False,
        validators=[validators.Optional()],  # required conditionally below
    )
    type_emploi_pro_studient = SelectField(
        "Type d'emploi pro",
        choices=[],
        validate_choice=False,
        validators=[validators.Optional()],
    )
    niveau_etude = SelectField(
        "Niveau d'étude",
        choices=[],
        validate_choice=False,
        validators=[validators.Optional()],
    )
    matiere_etudiee = SelectMultipleField(
        "Matières étudiées",
        choices=[],
        validate_choice=False,
        validators=[validators.Optional()],
    )
    langues = SelectMultipleField(
        "Langues",
        choices=[],
        validate_choice=False,
        validators=[validators.Optional()],
    )
    sector = SelectField(
        "Secteur d'activité",
        choices=[],
        validate_choice=False,
        validators=[validators.Optional()],
    )
    pays_zip_ville = CountrySelectField(
        name="pays_zip_ville",
        name2="pays_zip_ville_detail",
        label="Pays",
        id="pzv",
        id2="pzv_detail",
        label2="Code postal et ville",
        choices=[],
        validate_choice=False,
        readonly=0,
    )
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
    ending_date = DateField(
        "Date de fin de poste", validators=[validators.Optional()]
    )
    partial_time = IntegerField(
        "Temps partiel (%)", validators=[validators.Optional()]
    )

    def validate_domain_studient(self, field):
        """Domaine d'application is required only for student offers."""
        if self.statut.data == "STATUT / Etudiant.e" and not field.data:
            raise validators.ValidationError(
                "Veuillez choisir un domaine d'application."
            )


@blueprint.route("/jobs/new", methods=["GET", "POST"])
def jobs_new():
    user = cast(User, g.user)

    form = JobOfferForm(request.form)
    raw_statut_choices = cast(list, get_ontology_choices("type_job_statut"))
    statut_choices = [
        (val, strip_taxonomy_prefix(label)) for val, label in raw_statut_choices
    ]
    form.statut.choices = [("", "— Choisir un statut —"), *statut_choices]
    form.pays_zip_ville.choices = get_ontology_choices("country_pays")
    # #0230 — see missions_new: use the `field2` sub-dict so WTForms renders
    # optgroups instead of crashing on the dual-select {"field1", "field2"}.
    sector_choices = cast(dict, get_ontology_choices("multidual_secteurs_detail2"))
    form.sector.choices = sector_choices["field2"]
    domain_studient_choices = [
        (val, strip_taxonomy_prefix(label))
        for val, label in get_ontology_choices("type_job_studient_app")
    ]
    form.domain_studient.choices = [
        ("", "— Choisissez un domaine —"),
        *domain_studient_choices,
    ]
    form.type_emploi_pro_studient.choices = [
        ("", "— Choisissez un type d'emploi —"),
        *[
            (val, strip_taxonomy_prefix(label))
            for val, label in get_ontology_choices("type_job_studient")
        ],
    ]
    form.niveau_etude.choices = [
        ("", "— Choisissez un niveau —"),
        *[
            (val, strip_taxonomy_prefix(label))
            for val, label in get_ontology_choices("niveau_etude")
        ],
    ]
    form.matiere_etudiee.choices = [
        (val, label)
        for val, label in get_ontology_choices("matiere_etudiee")
    ]
    form.langues.choices = [
        (val, label)
        for val, label in get_ontology_choices("multi_langues")
    ]
    if request.method == "POST" and form.validate():
        contract_type = ContractType(form.contract_type.data or ContractType.CDI.value)

        # Check mission based on contract type
        match contract_type:
            case ContractType.STAGE:
                check_mission(user, PermissionType.INTERNSHIPS)
            case ContractType.APPRENTISSAGE:
                check_mission(user, PermissionType.APPRENTICESHIPS)
            case ContractType.DOCTORAL:
                check_mission(user, PermissionType.DOCTORAL)
            case _:
                if user.is_managing_another_bw:
                    raise Forbidden

        emitter_org_id = getattr(user, "organisation_id", None)
        if user.is_managing_another_bw:
            bw = get_selected_business_wall_for_user(user)
            if bw:
                emitter_org_id = bw.organisation_id

        job = JobOffer(
            title=form.title.data or "",
            description=form.description.data or "",
            statut=form.statut.data or "",
            domain_studient=list(form.domain_studient.data or []),
            type_emploi_pro_studient=list(form.type_emploi_pro_studient.data or []),
            niveau_etude=list(form.niveau_etude.data or []),
            matiere_etudiee=form.matiere_etudiee.data or [],
            langues=form.langues.data or [],
            sector=form.sector.data or "",
            pays_zip_ville=form.pays_zip_ville.data or "",
            pays_zip_ville_detail=request.form.get("pays_zip_ville_detail", ""),
            contract_type=contract_type,
            full_time=bool(form.full_time.data),
            remote_ok=bool(form.remote_ok.data),
            partial_time=form.partial_time.data,
            salary_min=euros_to_cents(form.salary_min.data),
            salary_max=euros_to_cents(form.salary_max.data),
            starting_date=date_to_datetime(form.starting_date.data),
            ending_date=date_to_datetime(form.ending_date.data),
            # contact_email left empty on new offers; notifications
            # fall back to owner.email. Ref bug #0073 item 4.
            status=default_new_offer_status(),
            mission_status=MissionStatus.OPEN,
            owner_id=user.id,
            emitter_org_id=emitter_org_id,
        )
        db.session.add(job)
        db.session.commit()
        if job.status == PublicationStatus.PUBLIC:
            marketplace_published.send(job)
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
