# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Marketplace — Projects (editorial projects) views."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import cast

from flask import flash, g, redirect, render_template, request, url_for
from wtforms import (
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
from app.models.lifecycle import PublicationStatus
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
from app.modules.bw.bw_activation.models import PermissionType
from app.modules.bw.bw_activation.user_utils import get_selected_business_wall_for_user
from app.modules.kyc.dynform import CountrySelectField
from app.modules.kyc.ontology_loader import get_choices as get_ontology_choices
from app.modules.wip.pr_access import check_mission
from app.services.taxonomies import get_taxonomy
from app.signals import marketplace_published

# Ticket #0198 — top-level project category, mirroring MissionCategory
# values. Kept as a separate constant (not the enum) because the source
# of truth is the admin-editable `type_projets` taxonomy ; this list
# is the form fallback when the ontology is empty.
_PROJECT_CATEGORY_VALUES: tuple[tuple[str, str], ...] = (
    ("journalisme", "Journalisme"),
    ("communication", "Communication"),
    ("innovation", "Innovation"),
)

# Per-category sub-type ontology slug, as defined by Erick in
# /admin/ontology/?taxonomy_name=type_projet_<cat>.
_PROJECT_SUBTYPE_TAXONOMIES: dict[str, str] = {
    "journalisme": "type_projet_journalisme",
    "communication": "type_projet_communication",
    "innovation": "type_projet_innovation",
}


def _build_category_choices(
    taxonomy_rows: Iterable[str],
) -> list[tuple[str, str]]:
    """Pure : given ontology rows, build the select choices.

    Always prefixes a blank entry. When the ontology is populated, use
    the rows as both value+label (the `type_projets` names are already
    display-ready French labels). When empty, fall back to the
    hardcoded `_PROJECT_CATEGORY_VALUES` triple.
    """
    rows = list(taxonomy_rows)
    if rows:
        return [("", "— Choisissez un type —"), *((r, r) for r in rows)]
    return [("", "— Choisissez un type —"), *list(_PROJECT_CATEGORY_VALUES)]


def get_project_category_choices() -> list[tuple[str, str]]:
    """Top-level project category select choices.

    Sourced from the `type_projets` taxonomy when populated, with the
    hardcoded triple as fallback. Always prefixes a blank entry so the
    select reads as optional.
    """
    try:
        rows = list(get_taxonomy("type_projets"))
    except Exception:
        rows = []
    return _build_category_choices(rows)


def _build_subtypes_for_taxonomies(
    loader: Callable[[str], Iterable[str]],
    taxonomies: dict[str, str],
) -> dict[str, list[str]]:
    """Pure : given a loader callable + the taxonomy-name mapping,
    return the per-category subtype lists.

    A loader exception on any taxonomy degrades to an empty list for
    that category — the template simply renders an empty select for
    that branch.
    """
    out: dict[str, list[str]] = {}
    for cat, taxonomy_name in taxonomies.items():
        try:
            out[cat] = list(loader(taxonomy_name))
        except Exception:
            out[cat] = []
    return out


def get_project_subtypes() -> dict[str, list[str]]:
    """Per-category sub-type lists for the Alpine cascade.

    Each value of `project_category` maps to a list of sub-type strings
    loaded from its taxonomy. Empty taxonomies stay empty.
    """
    return _build_subtypes_for_taxonomies(get_taxonomy, _PROJECT_SUBTYPE_TAXONOMIES)


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
    # Ticket #0198 — replace the legacy free-text « Type de projet »
    # with a cascading pair of ontology-backed selects.
    project_category = SelectField(
        "Type de projet",
        choices=[],  # populated per request
        validate_choice=False,
        validators=[validators.Optional()],
    )
    project_type = StringField(
        "Sous-type de projet",
        validators=[validators.Optional(), validators.Length(max=200)],
    )


@blueprint.route("/projects/new", methods=["GET", "POST"])
def projects_new():
    user = cast(User, g.user)
    check_mission(user, PermissionType.PROJECTS)

    form = ProjectOfferForm(request.form)
    form.pays_zip_ville.choices = get_ontology_choices("country_pays")
    form.project_category.choices = get_project_category_choices()
    if request.method == "POST" and form.validate():
        emitter_org_id = getattr(user, "organisation_id", None)
        if user.is_managing_another_bw:
            bw = get_selected_business_wall_for_user(user)
            if bw:
                emitter_org_id = bw.organisation_id

        project = ProjectOffer(
            title=form.title.data or "",
            description=form.description.data or "",
            sector=form.sector.data or "",
            pays_zip_ville=form.pays_zip_ville.data or "",
            pays_zip_ville_detail=request.form.get("pays_zip_ville_detail", ""),
            budget_min=euros_to_cents(form.budget_min.data),
            budget_max=euros_to_cents(form.budget_max.data),
            deadline=date_to_datetime(form.deadline.data),
            team_size=form.team_size.data,
            duration_months=form.duration_months.data,
            project_category=(form.project_category.data or "").strip(),
            project_type=(form.project_type.data or "").strip(),
            # contact_email left empty on new offers; notifications
            # fall back to owner.email. Ref bug #0073 item 4.
            status=default_new_offer_status(),
            mission_status=MissionStatus.OPEN,
            owner_id=user.id,
            emitter_org_id=emitter_org_id,
        )
        db.session.add(project)
        db.session.commit()
        if project.status == PublicationStatus.PUBLIC:
            marketplace_published.send(project)
        msg = (
            "Projet envoyé pour modération."
            if project.status.value == "pending"
            else "Projet publié."
        )
        flash(msg, "success")
        return redirect(url_for(".projects_detail", id=project.id))

    return render_template(
        "pages/projects/new.j2",
        form=form,
        title="Publier un projet",
        project_subtypes=get_project_subtypes(),
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
    message = (request.form.get("decision_message") or "").strip()
    return update_application_status(
        project,
        app_id,
        ApplicationStatus.SELECTED,
        ".projects_applications",
        decision_message=message,
    )


@blueprint.route(
    "/projects/<int:id>/applications/<int:app_id>/reject", methods=["POST"]
)
def projects_application_reject(id: int, app_id: int):
    project = get_offer_or_404(ProjectOffer, id)
    message = (request.form.get("decision_message") or "").strip()
    return update_application_status(
        project,
        app_id,
        ApplicationStatus.REJECTED,
        ".projects_applications",
        decision_message=message,
    )


@blueprint.route("/projects/<int:id>/fill", methods=["POST"])
def projects_fill(id: int):
    project = get_offer_or_404(ProjectOffer, id)
    return mark_filled(project, ".projects_detail")
