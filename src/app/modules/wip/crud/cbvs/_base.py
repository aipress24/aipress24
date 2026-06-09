# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import abc
from operator import itemgetter

from arrow import now
from flask import flash, g, redirect, request, url_for
from flask_classful import FlaskView, route
from sqlalchemy import select
from svcs.flask import container
from werkzeug import Response
from wtforms import Form as WTForm

from app.constants import LOCAL_TZ
from app.flask.extensions import db
from app.flask.lib.breadcrumbs import BreadCrumb
from app.flask.lib.htmx import extract_fragment
from app.flask.lib.templates import templated
from app.flask.lib.wtforms.renderer import FormRenderer
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.user_utils import (
    get_selected_business_wall_for_user,
)
from app.modules.kyc.ontology_loader import get_choices as get_ontology_choices
from app.modules.wip.crud.cbvs._table import BaseTable
from app.modules.wip.menu import make_menu
from app.services.context import Context
from app.services.menus import MenuService
from app.services.repositories import Repository

# language=jinja2
LIST_TEMPLATE = """
{% extends "wip/layout/_base.j2" %}
{% block body_content %}
  {{ table.render() }}
{% endblock %}
"""

# language=jinja2
UPDATE_TEMPLATE = """
{% extends "wip/layout/_base.j2" %}
{% block body_content %}
  {{ form_rendered|safe }}
{% endblock %}
"""

# language=jinja2
VIEW_TEMPLATE = """
{% extends "wip/layout/_base.j2" %}
{% block body_content %}
  {{ form_rendered|safe }}
  {{ extra_view_html|safe }}
{% endblock %}
"""


def get_name(obj):
    return obj.name if obj else ""


def _format_publisher_label(name: str) -> str:
    """Pure : wrap an organisation name in the standard publisher header.

    Centralising the format string keeps the « Publié pour le compte de … »
    header consistent across the three branches of `_resolve_publisher_text`.
    """
    return f'Publié pour le compte de "{name}"'


def _resolve_publisher_text(
    model,
    *,
    user_is_managing_another_bw: bool,
    selected_bw_name: str | None,
    user_org=None,
) -> str:
    """Pure core for the « Publié pour le compte de X » header.

    Bug #0135 : the header must follow the *model's own* publisher (the
    client an agency-member published *for*); the editing user's org is
    only the right fallback when creating a new model.

    The shell (`_view_ctx`) is responsible for resolving the runtime
    inputs (Flask `g.user`, `get_selected_business_wall_for_user`). The
    branching itself is pure and exhaustively unit-tested below.

    Args:
      model: the model being edited (or None for "new").
      user_is_managing_another_bw: snapshot of
        `g.user.is_managing_another_bw`.
      selected_bw_name: name of the currently-selected business wall,
        or None if the user is not managing another BW (or no BW is
        currently selected).
      user_org: the editing user's own organisation (or None).
    """
    model_publisher = getattr(model, "publisher", None) if model else None
    if model_publisher is not None:
        name = model_publisher.bw_name or model_publisher.name
        return _format_publisher_label(name)
    if user_is_managing_another_bw:
        if selected_bw_name:
            return _format_publisher_label(selected_bw_name)
        return ""
    if user_org is not None:
        name = user_org.bw_name or user_org.name
        return _format_publisher_label(name)
    return ""


def _build_index_breadcrumbs(
    *,
    work_url: str,
    label_list: str,
    index_url: str,
    extra_label: str = "",
    new_label: str | None = None,
) -> list[BreadCrumb]:
    """Pure : assemble the trail for index/new/edit pages.

    The shell resolves the URLs from Flask's `url_for`; this function
    just composes the standard prefix (`Work > <label_list>`) and
    appends the optional "new" and free-form crumbs.
    """
    crumbs = [
        BreadCrumb(label="Work", url=work_url),
        BreadCrumb(label=label_list, url=index_url),
    ]
    if new_label:
        crumbs.append(BreadCrumb(label=new_label, url=""))
    if extra_label:
        crumbs.append(BreadCrumb(label=extra_label, url=""))
    return crumbs


def _build_phase_breadcrumbs(
    *,
    work_url: str,
    label_list: str,
    index_url: str,
    model_title: str,
    model_url: str,
    phase: str,
) -> list[BreadCrumb]:
    """Pure : trail for a model sub-page (`Work > list > title > phase`).

    The `<titre>` crumb is clickable so the user can jump back to the
    detail view without going all the way up to the Work dashboard.
    Refs bugs #0070 (Avis d'enquête) and #0085 (article images).
    """
    return [
        BreadCrumb(label="Work", url=work_url),
        BreadCrumb(label=label_list, url=index_url),
        BreadCrumb(label=model_title, url=model_url),
        BreadCrumb(label=phase, url=""),
    ]


def _sort_org_choices(
    orgs,
    *,
    pinned_org=None,
) -> list[tuple[str, str]]:
    """Pure : turn `Organisation` rows into the (id, label) choices list.

    The list is sorted by display name; the optional `pinned_org` is
    inserted *first* so the editing user's own org always shows up at
    the top of the picker (with its `bw_name` label).
    """
    result = sorted([(str(org.id), org.name) for org in orgs], key=itemgetter(1))
    if pinned_org is not None:
        result.insert(0, (str(pinned_org.id), pinned_org.bw_name))
    return result


class BaseWipView(FlaskView, abc.ABC):
    name: str
    model_class: type
    form_class: type[WTForm]
    repo_class: type[Repository]
    table_class: type[BaseTable]
    doc_type: str

    # UI
    label_main: str
    label_list: str
    label_new: str
    label_edit: str
    label_view: str
    icon: str
    msg_delete_ok: str
    msg_delete_ko: str
    table_id: str

    route_prefix = "/wip/"

    def before_request(self, *_args, **_kwargs) -> Response | None:
        # Redirect unauthenticated users to login
        if not g.user.is_authenticated:
            return redirect(url_for("security.login"))

        menu_service = container.get(MenuService)
        menu_service.update(self._menus())
        return None

    def htmx(self) -> str:
        html = self.index().render()
        html = extract_fragment(html, id=self.table_id)
        return html

    def _make_table(self, q="") -> BaseTable:
        table = self.table_class(q)  # type: ignore[arg-type]
        table._action_url = self._url_for("htmx")  # type: ignore[attr-defined]
        table._new_url = f"/wip/{self.route_base}/new/"  # type: ignore[attr-defined]
        return table

    # Exposed methods
    @templated(LIST_TEMPLATE)
    def index(self) -> dict:
        q = request.args.get("q", "")
        self.update_breadcrumbs()
        return {
            "title": self.label_main,
            "table": self._make_table(q),
        }

    @templated(VIEW_TEMPLATE)
    def get(self, id):
        model = self._get_model(id)
        title = f"{self.label_view} '{model.title}'"
        return self._view_ctx(model, title=title, mode="view")

    @templated(UPDATE_TEMPLATE)
    def new(self) -> dict:
        return self._view_ctx(title=self.label_new)

    @templated(UPDATE_TEMPLATE)
    def edit(self, id):
        model = self._get_model(id)
        title = f"{self.label_edit} '{model.title}'"
        return self._view_ctx(model, title=title)

    def get_media_organisations(self) -> list[tuple[str, str]]:
        """Get list of media organisations (Sujet/Article/AvisEnquête target).

        Bug 0133: previously this also pulled organisations with `bw_id IS
        NULL` ("auto" placeholder orgs), so the picker drowned the real
        media in junk. Now scoped to organisations that have an ACTIVE BW
        of type "media" — i.e. those that actually subscribed to the
        Business Wall for Media plan and can therefore receive editorial
        proposals.
        """
        query = select(Organisation).where(
            Organisation.bw_id.is_not(None),
            Organisation.bw_active == "media",
        )
        query_result = db.session.execute(query).scalars()
        pinned_org = None
        if g.user.organisation_id:
            query2 = select(Organisation).where(
                Organisation.id == g.user.organisation_id
            )
            pinned_org = db.session.execute(query2).scalar()
        return _sort_org_choices(query_result, pinned_org=pinned_org)

    @templated(UPDATE_TEMPLATE)
    def post(self) -> Response | dict:
        repo = self._get_repo()

        form_data = request.form

        if form_data["_action"] == "cancel":
            return redirect(self._url_for("index"))

        form = self.form_class(form_data)

        self._make_media_choices(form)

        if not form.validate():
            return self._view_ctx(form=form)

        if id := request.form.get("id"):
            model = self._get_model(id)
        else:
            model = self.model_class()
            model.owner = g.user
            model.commanditaire_id = g.user.id

            if media_id_str := request.form.get("media_id"):
                org_id = int(media_id_str)
                model.media_id = int(org_id)

        form.populate_obj(model)

        if hasattr(model, "pays_zip_ville"):
            # load the second data field
            model.pays_zip_ville_detail = request.form.get("pays_zip_ville_detail", "")

        if hasattr(model, "media_id"):
            model.media_id = int(model.media_id)

        self._post_update_model(model)
        repo.add(model, auto_commit=True)

        flash("Enregistré")
        return redirect(self._url_for("index"))

    def _make_media_choices(self, form) -> None:
        if hasattr(form, "media_id"):
            form.media_id.choices = self.get_media_organisations()

    def _make_country_choices(self, form) -> None:
        if hasattr(form, "pays_zip_ville"):
            form.pays_zip_ville.choices = get_ontology_choices("country_pays")

    def _view_ctx(self, model=None, form=None, mode="edit", title=""):
        self.update_breadcrumbs(label=title)

        if not form:
            form = self.form_class(obj=model)

        endpoint = f"{self.__class__.__name__}:post"

        self._make_media_choices(form)
        self._make_country_choices(form)

        if hasattr(form, "pays_zip_ville"):
            # load second data field
            if model:
                form.pays_zip_ville.data2 = model.pays_zip_ville_detail  # type: ignore[attr-defined]
            if mode == "view":
                form.pays_zip_ville.lock = 1  # type: ignore[attr-defined]
            else:
                form.pays_zip_ville.lock = 0  # type: ignore[attr-defined]

        # Bug #0135 : delegate the branching to a pure helper. The
        # shell only resolves the runtime inputs (current user, its
        # selected business wall) — the textual contract itself is
        # unit-tested directly via `_resolve_publisher_text`.
        user_is_managing_another_bw = getattr(g.user, "is_managing_another_bw", False)
        selected_bw_name: str | None = None
        if user_is_managing_another_bw:
            bw = get_selected_business_wall_for_user(g.user)
            if bw:
                selected_bw_name = bw.name
        publisher_text = _resolve_publisher_text(
            model,
            user_is_managing_another_bw=user_is_managing_another_bw,
            selected_bw_name=selected_bw_name,
            user_org=getattr(g.user, "organisation", None),
        )

        renderer = FormRenderer(
            form,
            model=model,
            mode=mode,
            action_url=url_for(endpoint),
        )

        return {
            "title": title,
            "publisher_text": publisher_text,
            "form_rendered": renderer.render(),
            "extra_view_html": self._extra_view_html(model, mode),
        }

    def _extra_view_html(self, model, mode: str) -> str:
        """Hook for subclasses to inject HTML below the form (view mode only).

        Default returns an empty string. Subclasses may override to render
        e.g. an image gallery in view mode that the form itself doesn't
        cover.
        """
        del model, mode
        return ""

    def _update_model(self, form, model) -> None:
        repo = self._get_repo()

        if not model:
            model = self.model_class()
            model.owner = g.user
            # FIXME
            model.media = g.user.organisation
            model.commanditaire_id = g.user.id

        form.populate_obj(model)
        self._post_update_model(model)

        repo.add(model, auto_commit=True)

    @route("/<id>/delete", methods=["GET"])
    def delete(self, id):
        repo = self._get_repo()
        model = self._get_model(id)

        if model.owner != g.user:
            flash(self.msg_delete_ko)
            return redirect(self._url_for("index"))

        model.deleted_at = now(LOCAL_TZ)
        repo.update(model, auto_commit=True)

        flash(self.msg_delete_ok)
        return redirect(self._url_for("index"))

    # Common methods

    def _post_update_model(self, model) -> None:
        """Implemented in subclass, if neeeded"""

    def _url_for(self, _action="get", **kwargs):
        class_name = self.__class__.__name__
        return url_for(f"{class_name}:{_action}", **kwargs)

    def _menus(self):
        return {
            "secondary": make_menu(self.name),
        }

    def update_breadcrumbs(self, key="", label="") -> None:
        context = container.get(Context)
        breadcrumbs = _build_index_breadcrumbs(
            work_url=url_for("wip.wip"),
            label_list=self.label_list,
            index_url=self._url_for("index"),
            extra_label=label,
            new_label=self.label_new if key == "new" else None,
        )
        context.update(breadcrumbs=breadcrumbs)

    def update_phase_breadcrumbs(self, model, phase: str) -> None:
        """Breadcrumb for a sub-page of a model (images, ciblage, …).

        Produces:
          `Work > <label_list> > <model.title> (lien vers détail) > <phase>`

        The `<titre>` crumb is clickable and points to the detail view —
        it lets the user come back to the "⋯" menu from any sub-page
        without going all the way up to the Work dashboard. Refs bugs
        #0070 (Avis d'enquête) and #0085 (article images).
        """
        context = container.get(Context)
        breadcrumbs = _build_phase_breadcrumbs(
            work_url=url_for("wip.wip"),
            label_list=self.label_list,
            index_url=self._url_for("index"),
            model_title=model.title,
            model_url=self._url_for("get", id=model.id),
            phase=phase,
        )
        context.update(breadcrumbs=breadcrumbs)

    def _get_repo(self):
        return container.get(self.repo_class)

    def _get_model(self, id):
        repo = self._get_repo()
        return repo.get(id)
