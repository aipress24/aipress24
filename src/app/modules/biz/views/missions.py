# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Marketplace — Missions (piges / freelance) views."""

from __future__ import annotations

from typing import cast

from flask import flash, g, redirect, render_template, request, url_for
from werkzeug.exceptions import NotFound
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

from app.enums import RoleEnum
from app.flask.extensions import db
from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.modules.biz import blueprint
from app.modules.biz.models import (
    ApplicationStatus,
    MissionCategory,
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
from app.modules.bw.bw_activation.models import PermissionType
from app.modules.bw.bw_activation.user_utils import get_selected_business_wall_for_user
from app.modules.kyc.dynform import CountrySelectField
from app.modules.kyc.ontology_loader import get_choices as get_ontology_choices
from app.modules.wip.pr_access import check_mission
from app.services.roles import has_role
from app.signals import marketplace_published

# Bug #0185 — top-level Mission sub-typing. The 3 categories Erick
# spelled out, with per-category placeholder sub-lists kept until the
# `type_mission_*` ontologies land. Wire format = StrEnum lowercase
# name (`MissionCategory(...).value`), shared with the form, the URL
# state, and the DB column.
_CATEGORY_CHOICES: list[tuple[str, str]] = [
    ("", "— Choisissez une catégorie —"),
    (MissionCategory.JOURNALISME.value, "Journalisme"),
    (MissionCategory.COMMUNICATION.value, "Communication"),
    (MissionCategory.INNOVATION.value, "Innovation"),
]

# Placeholder sub-lists per category, exposed to the template so the
# dynamic Alpine.js selector can mount only the relevant one.
MISSION_SUBCATEGORIES: dict[str, list[str]] = {
    MissionCategory.JOURNALISME.value: [
        "Pige / Reportage",
        "Enquête",
        "Interview",
        "Couverture d'événement",
        "Édition / Secrétariat de rédaction",
    ],
    MissionCategory.COMMUNICATION.value: [
        "Communiqué de presse",
        "Conférence de presse / Événement",
        "Campagne RP",
        "Réseaux sociaux",
        "Stratégie / Conseil",
    ],
    MissionCategory.INNOVATION.value: [
        "Outil IA",
        "Newsletter / Plateforme",
        "Format vidéo / podcast",
        "Recherche / Étude",
        "Outil de gestion éditoriale",
    ],
}


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
    # Bug #0185 — top-level category + per-category sub-type. Both
    # are optional in the form layer to preserve back-compat with the
    # existing tests / clients ; the UI strongly invites the user to
    # fill them.
    category = SelectField(
        "Type de mission",
        choices=_CATEGORY_CHOICES,
        validators=[validators.Optional()],
    )
    subcategory = StringField(
        "Sous-type",
        validators=[validators.Optional(), validators.Length(max=200)],
    )
    # Bug #0187 — Journalism extension : 8 taxonomy fields backed by
    # KYC ontologies + 2 work-mode flags. Persisted as JSON lists /
    # booleans on the model. The deposit template only renders them
    # when the chosen category is « journalisme » (Alpine wrapper).
    # Choices are populated at request time from the ontology
    # registry ; `validate_choice=False` keeps the form lenient if a
    # taxonomy entry was renamed between the GET and the POST.
    metiers_journalisme = SelectMultipleField(
        "Métiers du journalisme",
        choices=[],
        validate_choice=False,
        validators=[validators.Optional()],
    )
    types_entreprises_presse_medias = SelectMultipleField(
        "Types d'entreprises de presse & médias",
        choices=[],
        validate_choice=False,
        validators=[validators.Optional()],
    )
    types_presse_medias = SelectMultipleField(
        "Types presse & médias",
        choices=[],
        validate_choice=False,
        validators=[validators.Optional()],
    )
    competences_journalisme = SelectMultipleField(
        "Compétences en journalisme",
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
    types_contenus_editoriaux = SelectMultipleField(
        "Types de contenus éditoriaux",
        choices=[],
        validate_choice=False,
        validators=[validators.Optional()],
    )
    taille_contenus_editoriaux = SelectMultipleField(
        "Taille des contenus éditoriaux",
        choices=[],
        validate_choice=False,
        validators=[validators.Optional()],
    )
    modes_remuneration = SelectMultipleField(
        "Modes de rémunération",
        choices=[],
        validate_choice=False,
        validators=[validators.Optional()],
    )
    physical_required = BooleanField(
        "La mission doit s'effectuer physiquement à l'emplacement indiqué",
        default=False,
    )
    remote_required = BooleanField(
        "La mission doit s'effectuer en télétravail", default=False
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
    budget_min = IntegerField("Budget min (€)", validators=[validators.Optional()])
    budget_max = IntegerField("Budget max (€)", validators=[validators.Optional()])
    deadline = DateField("Date limite", validators=[validators.Optional()])


_JOURNALISM_TAXONOMY_FIELDS: tuple[tuple[str, str], ...] = (
    # (form field name, ontology field-type key)
    ("metiers_journalisme", "multi_fonctions_journalisme"),
    ("types_entreprises_presse_medias", "multi_type_entreprise_medias"),
    ("types_presse_medias", "multi_type_media"),
    ("competences_journalisme", "multi_competences_journalisme"),
    ("langues", "multi_langues"),
    ("types_contenus_editoriaux", "multi_type_contenu"),
    ("taille_contenus_editoriaux", "multi_taille_contenu"),
    ("modes_remuneration", "multi_mode_remuneration"),
)


def _populate_journalism_taxonomy_choices(form: MissionOfferForm) -> None:
    """Bug #0187 — wire each Journalism multi-select to its ontology.

    `get_ontology_choices` returns a list of `(value, name)` tuples,
    matching what WTForms `SelectMultipleField` expects. Failures are
    swallowed so a missing taxonomy doesn't take down the whole
    deposit form — the offending field then just has no options.
    """
    for field_name, ontology_key in _JOURNALISM_TAXONOMY_FIELDS:
        try:
            choices = get_ontology_choices(ontology_key)
        except Exception:
            choices = []
        if isinstance(choices, list):
            getattr(form, field_name).choices = choices
        else:
            getattr(form, field_name).choices = []


@blueprint.route("/missions/new", methods=["GET", "POST"])
def missions_new():
    user = cast(User, g.user)
    check_mission(user, PermissionType.MISSIONS)

    form = MissionOfferForm(request.form)
    form.pays_zip_ville.choices = get_ontology_choices("country_pays")
    _populate_journalism_taxonomy_choices(form)
    if request.method == "POST" and form.validate():
        emitter_org_id = getattr(user, "organisation_id", None)
        if user.is_managing_another_bw:
            bw = get_selected_business_wall_for_user(user)
            if bw:
                emitter_org_id = bw.organisation_id

        # Bug #0185 — category is optional ; map the empty form
        # value to None on the model.
        category_value = (form.category.data or "").strip()
        category: MissionCategory | None
        if category_value:
            try:
                category = MissionCategory(category_value)
            except ValueError:
                category = None
        else:
            category = None

        # Bug #0186 — only journalists may publish Journalism
        # missions. Strip the category silently and flash a hint
        # instead of crashing so the rest of the form is still useful
        # (the user can lower their ambition to Communication /
        # Innovation if they wish).
        if category == MissionCategory.JOURNALISME and not has_role(
            user, RoleEnum.PRESS_MEDIA
        ):
            flash(
                "Les missions Journalisme sont réservées aux journalistes.",
                "error",
            )
            return render_template(
                "pages/missions/new.j2",
                form=form,
                title="Publier une mission",
                mission_subcategories=MISSION_SUBCATEGORIES,
            )

        # Bug #0187 — `SelectMultipleField.data` is already a clean
        # list of selected ontology values ; no normalisation needed.
        mission = MissionOffer(
            title=form.title.data or "",
            description=form.description.data or "",
            sector=form.sector.data or "",
            category=category,
            subcategory=(form.subcategory.data or "").strip(),
            metiers_journalisme=list(form.metiers_journalisme.data or []),
            types_entreprises_presse_medias=list(
                form.types_entreprises_presse_medias.data or []
            ),
            types_presse_medias=list(form.types_presse_medias.data or []),
            competences_journalisme=list(form.competences_journalisme.data or []),
            langues=list(form.langues.data or []),
            types_contenus_editoriaux=list(form.types_contenus_editoriaux.data or []),
            taille_contenus_editoriaux=list(form.taille_contenus_editoriaux.data or []),
            modes_remuneration=list(form.modes_remuneration.data or []),
            physical_required=bool(form.physical_required.data),
            remote_required=bool(form.remote_required.data),
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
            emitter_org_id=emitter_org_id,
        )
        db.session.add(mission)
        db.session.commit()
        if mission.status == PublicationStatus.PUBLIC:
            marketplace_published.send(mission)
        msg = (
            "Mission envoyée pour modération."
            if mission.status.value == "pending"
            else "Mission publiée."
        )
        flash(msg, "success")
        return redirect(url_for(".missions_detail", id=mission.id))

    return render_template(
        "pages/missions/new.j2",
        form=form,
        title="Publier une mission",
        # Bug #0185 — handed to the template so Alpine can mount the
        # right sub-category select based on the chosen category.
        mission_subcategories=MISSION_SUBCATEGORIES,
    )


def _enforce_journalism_visibility(mission: MissionOffer) -> None:
    """Bug #0186 — Journalism missions are only visible to PRESS_MEDIA.

    Abort 404 (not 403) so non-journalists can't probe for the
    existence of restricted missions. Per Erick : « les autres
    communautés n'ont pas à savoir ce que postent les journalistes ».
    """
    if mission.category != MissionCategory.JOURNALISME:
        return
    if not has_role(g.user, RoleEnum.PRESS_MEDIA):
        raise NotFound


@blueprint.route("/missions/<int:id>")
def missions_detail(id: int):
    mission = get_offer_or_404(MissionOffer, id)
    _enforce_journalism_visibility(mission)
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
    _enforce_journalism_visibility(mission)
    return handle_apply(mission, detail_endpoint=".missions_detail")


@blueprint.route("/missions/<int:id>/applications")
def missions_applications(id: int):
    mission = get_offer_or_404(MissionOffer, id)
    _enforce_journalism_visibility(mission)
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
