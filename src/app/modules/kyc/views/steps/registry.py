# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import importlib

from werkzeug.utils import find_modules

from app.modules.kyc.views.steps import Step

ROOT_MODULE = "app.modules.kyc.views.steps"


class StepRegistry:
    def __init__(self):
        self.registered = []

    def add(self, name, ob):
        self.registered.append((name, ob))

    def get_step(self, step_id: str) -> Step:
        for id, step in self.registered:
            if id == step_id:
                return step

        raise ValueError(f"Step {step_id} not found")


step_registry = StepRegistry()


def scan_steps():
    module_names = list(find_modules(ROOT_MODULE, True, True))
    for module_name in module_names:
        scan_module(module_name)


def scan_module(module_name: str):
    module = importlib.import_module(module_name)

    for obj in vars(module).values():
        if isinstance(obj, type) and issubclass(obj, Step):
            step = obj()
            step_registry.add(step.id, step)


scan_steps()
