# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import webargs
from flask import url_for

from app.flask.lib.breadcrumbs import BreadCrumb
from app.models.meta import get_label

from .base_view import View


class DetailView(View):
    ARGS = {
        "id": webargs.fields.Str(load_default=None),
        "doc_type": webargs.fields.Str(load_default=None),
    }

    def context_for_get(self):
        type_label = get_label(self.model)
        title = f"{type_label}: {self.model.title}"
        breadcrumbs = [
            BreadCrumb(
                url=url_for("wip.contents", mode="list"), label="Liste des contenus"
            ),
        ]
        return {
            "_template_str": self._get_template(),
            "obj": self.model,
            "title": title,
            "form": self.form,
            "breadcrumbs2": breadcrumbs,
            "stats": self.get_stats(),
        }

    def get_stats(self):
        keys = ["num_likes", "num_replies", "num_views", "num_comments"]
        stats = {k: getattr(self.model, k, 0) for k in keys}
        return stats
