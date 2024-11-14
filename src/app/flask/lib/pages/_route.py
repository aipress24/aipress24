# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from dataclasses import dataclass

from flask import request


@dataclass
class Route:
    def __init__(self, page_class, method_name=""):
        self.page_class = page_class
        self.method_name = method_name

    def __call__(self, **kwargs):
        page = self.page_class(**kwargs)

        if self.method_name:
            return getattr(page, self.method_name)()

        match request.method:
            case "GET":
                return page.get()
            case "POST":
                return page.post()

    @property
    def path(self):
        if self.method_name:
            return self.page_class.path + "/" + self.method_name
        else:
            return self.page_class.path

    @property
    def endpoint(self):
        if self.method_name:
            return self.page_class.name + "__" + self.method_name
        else:
            return self.page_class.name

    @property
    def __name__(self):
        if self.method_name:
            return self.page_class.__name__ + "__" + self.method_name
        else:
            return self.page_class.__name__
