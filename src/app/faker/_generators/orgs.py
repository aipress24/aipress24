# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import random

from mimesis import Person

from app.faker._constants import ORGANISATIONS
from app.models.organisation import Organisation

from .base import BaseGenerator, faker


class OrgGenerator(BaseGenerator):
    """Generate BW official organisation."""

    def __post_init__(self) -> None:
        super().__post_init__()
        self.person_faker = Person(self.locale)

    def make_obj(self):
        def _random_name() -> str:
            while True:
                if random.random() < 0.5:
                    name = faker.company()
                else:
                    name = random.choice(ORGANISATIONS)
                if name not in {org.name for org in self.objects}:
                    break
            return name

        org = Organisation(name=_random_name())
        self._set_basic_info(org)
        # self._set_business_wall_type(org)

        return org

    def _set_basic_info(self, org: Organisation) -> None:
        """Set basic organization information."""
        org.karma = random.randint(1, 10)

    # def _set_business_wall_type(self, org: Organisation) -> None:
    #     """Set business wall subscription type randomly."""
    #     org.bw_type = random.choice(
    #         list(BWTypeEnum)
    #     )
