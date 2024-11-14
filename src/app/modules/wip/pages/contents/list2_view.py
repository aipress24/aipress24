# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from .base_view import View


class ListView(View):
    def context_for_get(self):
        return {
            "_template_str": self._get_template(),
        }

    # def context_for_get(self):
    #     type_label = get_label(self.model)
    #     title = f"{type_label}: {self.model.title}"
    #     breadcrumbs = [
    #         BreadCrumb(
    #             url=url_for("wip.contents", mode="list"), label="Liste des contenus"
    #         ),
    #     ]
    #     return {
    #         "_template_str": self._get_template(),
    #         "obj": self.model,
    #         "title": title,
    #         "form": self.form,
    #         "breadcrumbs2": breadcrumbs,
    #         "stats": self.get_stats(),
    #     }
