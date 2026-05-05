# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Marketplace — Missions (piges / freelance) views."""

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
    MissionOffer,
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
    update_application_status,
)
from app.modules.kyc.dynform import CountrySelectField
from app.modules.kyc.ontology_loader import get_choices as get_ontology_choices


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


@blueprint.route("/missions/new", methods=["GET", "POST"])
def missions_new():
    user = cast(User, g.user)

    form = MissionOfferForm(request.form)
    form.pays_zip_ville.choices = get_ontology_choices("country_pays")
    if request.method == "POST" and form.validate():
        mission = MissionOffer(
            title=form.title.data or "",
            description=form.description.data or "",
            sector=form.sector.data or "",
            pays_zip_ville=form.pays_zip_ville.data or "",
            pays_zip_ville_detail=request.form.get("pays_zip_ville_detail", ""),
            budget_min=euros_to_cents(form.budget_min.data),
            budget_max=euros_to_cents(form.budget_max.data),
            deadline=date_to_datetime(form.deadline.data),
            # contact_email left empty on new offers; notifications
            # fall back to owner.email (cf. _pick_emitter_email). Ref bug
            # #0073 item 4.
            status=default_new_offer_status(),
            mission_status=MissionStatus.OPEN,
            owner_id=user.id,
            emitter_org_id=getattr(user, "organisation_id", None),
        )
        db.session.add(mission)
        db.session.commit()
        msg = (
            "Mission envoyée pour modération."
            if mission.status.value == "pending"
            else "Mission publiée."
        )
        flash(msg, "success")
        return redirect(url_for(".missions_detail", id=mission.id))

    return render_template(
        "pages/missions/new.j2", form=form, title="Publier une mission"
    )


@blueprint.route("/missions/<int:id>")
def missions_detail(id: int):
    mission = get_offer_or_404(MissionOffer, id)
    user = cast(User, g.user)

    user_application = None
    if not user.is_anonymous and user.id != mission.owner_id:
        user_application = get_user_application(mission.id, user)

    return render_template(
        "pages/missions/detail.j2",
        mission=mission,
        user_application=user_application,
        is_owner=(not user.is_anonymous and user.id == mission.owner_id),
        title=mission.title,
    )


@blueprint.route("/missions/<int:id>/apply", methods=["POST"])
def missions_apply(id: int):
    mission = get_offer_or_404(MissionOffer, id)
    return handle_apply(mission, detail_endpoint=".missions_detail")


@blueprint.route("/missions/<int:id>/applications")
def missions_applications(id: int):
    mission = get_offer_or_404(MissionOffer, id)
    from app.modules.biz.views._offers_common import require_owner

    require_owner(mission)
    return render_template(
        "pages/missions/applications.j2",
        mission=mission,
        applications=list_applications(mission),
        title=f"Candidatures — {mission.title}",
    )


@blueprint.route(
    "/missions/<int:id>/applications/<int:app_id>/select",
    methods=["POST"],
)
def missions_application_select(id: int, app_id: int):
    mission = get_offer_or_404(MissionOffer, id)
    return update_application_status(
        mission, app_id, ApplicationStatus.SELECTED, ".missions_applications"
    )


@blueprint.route(
    "/missions/<int:id>/applications/<int:app_id>/reject",
    methods=["POST"],
)
def missions_application_reject(id: int, app_id: int):
    mission = get_offer_or_404(MissionOffer, id)
    return update_application_status(
        mission, app_id, ApplicationStatus.REJECTED, ".missions_applications"
    )


@blueprint.route("/missions/<int:id>/fill", methods=["POST"])
def missions_fill(id: int):
    mission = get_offer_or_404(MissionOffer, id)
    return mark_filled(mission, ".missions_detail")
