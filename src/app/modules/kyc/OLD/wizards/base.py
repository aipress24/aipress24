# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

# from __future__ import annotations
#
# from markdown import markdown
# from markupsafe import Markup
#
# from app.lib.names import to_kebab_case
#
#
# class WizardStep:
#     title: str = ""
#     postscript_md: str = ""
#     preamble_md: str = ""
#     questions: list[str] = []
#
#     is_first: bool = False
#     previous: type[WizardStep] | None = None
#
#     @property
#     def id(self) -> str:
#         return to_kebab_case(self.__class__.__name__)
#
#     @property
#     def previous_step_id(self) -> str:
#         if self.previous:
#             return to_kebab_case(self.previous.__name__)
#         return ""
#
#     @property
#     def is_end(self) -> bool:
#         return bool(self.postscript_md)
#
#     @property
#     def preamble(self) -> str:
#         return Markup(markdown(self.preamble_md))
#
#     @property
#     def postscript(self) -> str:
#         return Markup(markdown(self.postscript_md))
