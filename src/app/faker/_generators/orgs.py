# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import random
from pathlib import Path

from mimesis import Person

from app.enums import OrganisationTypeEnum
from app.models.organisation import Organisation

from .._constants import COVER_IMAGES, ORGANISATIONS
from .._geo import fake_geoloc
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

        def _random_non_auto_type() -> OrganisationTypeEnum:
            while True:
                family = random.choice(list(OrganisationTypeEnum))  #
                if family != OrganisationTypeEnum.AUTO:
                    break
            return family

        org = Organisation(name=_random_name(), type=_random_non_auto_type())

        org.description = self.generate_html(min_sentences=1, max_sentences=3)
        org.domain = faker.domain_name()
        org.site_url = fake_agency_url()
        org.jobs_url = faker.url()
        org.github_url = faker.url()
        org.linkedin_url = faker.url()

        id = random.randint(1, 14)
        org.logo_url = f"/static/tmp/logos/{id}.png"
        org.cover_image_url = random.choice(COVER_IMAGES)
        fake_geoloc(org)

        if org.type == OrganisationTypeEnum.AGENCY:
            org.agree_cppap = random.random() < 0.5
            match random.randint(0, 3):
                case 0:
                    org.membre_sapi = True
                case 1:
                    org.membre_satev = True
                case 2:
                    org.membre_saphir = True

        return org


def fake_agency_url():
    lines = Path("data/sites-web.txt").read_text().split("\n")
    lines = [line for line in lines if line]
    return random.choice(lines)
