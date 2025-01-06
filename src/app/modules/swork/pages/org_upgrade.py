# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

# from app.flask.lib.pages import Page
# from app.flask.sqla import get_obj
# from app.models.organisation import Organisation
#
# from .organisations import OrgsPage, OrgVM
#
#
# class OrgUpgradePage(Page):
#     layout = "layout/private.j2"
#     name = "org_upgrade"
#     path = "/orgs/<int:id>/upgrade"
#     template = "pages/org-upgrade.j2"
#
#     parent = OrgsPage
#
#     def __init__(self, id: int):
#         self.args = {"id": id}
#         self.org = get_obj(id, Organisation)
#
#     @property
#     def label(self):
#         return self.org.name
#
#     def context(self):
#         vm = OrgVM(self.org)
#         return {
#             "org": vm,
#         }
