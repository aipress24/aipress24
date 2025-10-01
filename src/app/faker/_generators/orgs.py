# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import random
from pathlib import Path

from mimesis import Person
import urllib.request

from app.enums import BWTypeEnum, OrganisationTypeEnum
from app.faker._constants import COVER_IMAGES, ORGANISATIONS
from app.faker._geo import fake_geoloc
from app.models.organisation import Organisation
from app.modules.kyc.resized import squared
from app.modules.wip.pages.business_wall.business_wall_form import add_blob_image

from .base import BaseGenerator, faker
from .users import random_taille_orga


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

        org.description = self.generate_text(max_length=1200)
        org.site_url = fake_agency_url()

        org.siren = str(random.randint(100000000, 999999999))
        org.tva = f"FR {random.randint(10, 99)} {org.siren}"
        org.tel_standard = self.person_faker.telephone()
        org.taille_orga = random_taille_orga()
        org.karma = random.randint(1, 10)

        idx = random.randint(1, 14)
        # org.logo_url = f"/static/tmp/logos/{idx}.png"
        logo_content = Path(f"src/app/static/tmp/logos/{idx}.png").read_bytes()
        org.logo_id = add_blob_image(squared(logo_content))
        cover_content = urllib.request.urlopen(random.choice(COVER_IMAGES)).read()  # noqa: S310
        org.cover_image_id = add_blob_image(cover_content)
        # org.cover_image_url = random.choice(COVER_IMAGES)
        org.cover_image_id = ""
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

        # official oraganisation have a subscription to a BW
        match org.type:
            case OrganisationTypeEnum.AUTO:
                pass
            case OrganisationTypeEnum.MEDIA:
                org.bw_type = BWTypeEnum.MEDIA
            case OrganisationTypeEnum.AGENCY:
                org.bw_type = BWTypeEnum.AGENCY
            case OrganisationTypeEnum.COM:
                org.bw_type = BWTypeEnum.COM
            case OrganisationTypeEnum.OTHER:
                org.bw_type = random.choice(
                    (
                        BWTypeEnum.CORPORATE,
                        BWTypeEnum.PRESSUNION,
                        BWTypeEnum.ORGANISATION,
                        BWTypeEnum.TRANSFORMER,
                        BWTypeEnum.ACADEMICS,
                    )
                )

        return org


def fake_agency_url():
    lines = Path("bootstrap_data/sites-web.txt").read_text().split("\n")
    lines = [line for line in lines if line]
    return random.choice(lines)
