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
from app.enums import OrganisationTypeEnum
from app.flask.extensions import db
from app.flask.lib.breadcrumbs import BreadCrumb
from app.flask.lib.htmx import extract_fragment
from app.flask.lib.templates import templated
from app.flask.lib.wtforms.renderer import FormRenderer
from app.models.organisation import Organisation
from app.modules.wip.crud.cbvs._table import BaseTable
from app.modules.wip.menu import make_menu
from app.services.blobs import BlobService
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
{% endblock %}
"""


def get_name(obj):
    return obj.name if obj else ""


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

    def before_request(self, *_args, **_kwargs) -> None:
        menu_service = container.get(MenuService)
        menu_service.update(self._menus())

    def htmx(self) -> str:
        html = self.index().render()
        html = extract_fragment(html, id=self.table_id)
        return html

    def _make_table(self, q="") -> BaseTable:
        table = self.table_class(q)
        table._action_url = self._url_for("htmx")
        table._new_url = f"/wip/{self.route_base}/new/"
        return table

    # Exposed methods
    @templated(LIST_TEMPLATE)
    def index(self) -> dict:
        q = request.args.get("q")
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
        """Get list of Organisation and their ID of type MEDIA AGENCY and AUTO.

        List not filtered for duplicates.
        """
        query = select(Organisation).where(
            Organisation.type.in_(
                [
                    OrganisationTypeEnum.MEDIA,
                    OrganisationTypeEnum.AGENCY,
                    OrganisationTypeEnum.OTHER,
                    OrganisationTypeEnum.AUTO,
                ]
            )
        )
        query_result = db.session.execute(query).scalars()
        result = sorted(
            [(str(org.id), org.name) for org in query_result], key=itemgetter(1)
        )
        if g.user.organisation_id:
            query2 = select(Organisation).where(
                Organisation.id == g.user.organisation_id
            )
            user_org = db.session.execute(query2).scalar()
            if user_org:
                result.insert(0, (str(user_org.id), user_org.name))
        return result

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

        if hasattr(model, "media_id"):
            model.media_id = int(model.media_id)

        self._post_update_model(model)
        repo.add(model, auto_commit=True)

        flash("Enregistré")
        return redirect(self._url_for("index"))

    def _make_media_choices(self, form) -> None:
        if hasattr(form, "media_id"):
            form.media_id.choices = self.get_media_organisations()

    def _view_ctx(self, model=None, form=None, mode="edit", title=""):
        self.update_breadcrumbs(label=title)

        if not form:
            form = self.form_class(obj=model)

        endpoint = f"{self.__class__.__name__}:post"

        self._make_media_choices(form)

        renderer = FormRenderer(
            form,
            model=model,
            mode=mode,
            action_url=url_for(endpoint),
        )

        return {
            "title": title,
            "form_rendered": renderer.render(),
        }

    def _update_model(self, form, model) -> None:
        repo = self._get_repo()

        if not model:
            model = self.model_class()
            model.owner = g.user
            # FIXME
            model.media = g.user.organisation
            model.commanditaire_id = g.user.id

        blob_service = container.get(BlobService)
        files = request.files
        # FIXME
        if "image" in files:
            blob = blob_service.save(files["image"])
            if blob.size > 0:
                model.image_id = blob.id

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
        breadcrumbs = [
            BreadCrumb(
                label="Work",
                url=url_for("wip.wip"),
            ),
            BreadCrumb(
                label=self.label_list,
                url=self._url_for("index"),
            ),
        ]
        if key == "new":
            bc = BreadCrumb(label=self.label_new, url="")
            breadcrumbs.append(bc)
        if label:
            bc = BreadCrumb(label=label, url="")
            breadcrumbs.append(bc)

        context.update(breadcrumbs=breadcrumbs)

    def _get_repo(self):
        return container.get(self.repo_class)

    def _get_model(self, id):
        repo = self._get_repo()
        return repo.get(id)
