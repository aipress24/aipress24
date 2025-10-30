# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import flash, g, request
from flask_login import current_user
from werkzeug.utils import redirect

from app.flask.extensions import db
from app.flask.lib.pages import page
from app.flask.routing import url_for
from app.modules.common.blob_utils import add_blob_content
from app.settings.constants import MAX_IMAGE_SIZE

from .base import BasePreferencesPage
from .home import PrefHomePage


@page
class PrefBannerPage(BasePreferencesPage):
    parent = PrefHomePage
    name = "banner"
    label = "Image de présentation"
    template = "pages/preferences/banner.j2"
    icon = "sparkles"

    def get_cover_image_url(self) -> str:
        user = g.user
        if not user.cover_image_id:
            return ""
        return url_for("api.get_blob", id=user.cover_image_id)

    def context(self) -> dict[str, str]:
        current_image_url = self.get_cover_image_url()
        return {"current_image_url": current_image_url}

    def post(self):
        if not current_user.is_authenticated:
            msg = "No currently authenticated user"
            raise ValueError(msg)

        if request.form.get("submit") == "cancel":
            return redirect(url_for(f".{self.name}"))

        uploaded_image = request.files.get("image")
        if uploaded_image and uploaded_image.filename:
            content = request.files["image"].read()
            if len(content) < MAX_IMAGE_SIZE:
                blob_id = add_blob_content(content)
                user = g.user
                user.cover_image_id = blob_id
                db.session.merge(user)
                db.session.commit()
            else:
                flash("L'image est trop volumineuse")
        return redirect(url_for(f".{self.name}"))
