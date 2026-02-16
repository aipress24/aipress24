# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import random
import urllib.request
from pathlib import Path

from mimesis import Person

from app.enums import BWTypeEnum, OrganisationTypeEnum
from app.faker._constants import COVER_IMAGES, ORGANISATIONS
from app.faker._geo import fake_geoloc
from app.lib.file_object_utils import create_file_object
from app.lib.image_utils import resized, squared
from app.models.organisation import Organisation

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
                family = random.choice(list(OrganisationTypeEnum))  # type: ignore[arg-type]
                if family != OrganisationTypeEnum.AUTO:
                    break
            return family

        org = Organisation(name=_random_name(), type=_random_non_auto_type())

        self._set_basic_info(org)
        self._set_images(org)
        self._set_agency_specific_info(org)
        self._set_business_wall_type(org)

        return org

    def _set_basic_info(self, org: Organisation) -> None:
        """Set basic organization information."""
        org.description = self.generate_text(max_length=1200)
        org.site_url = fake_agency_url()
        org.siren = str(random.randint(100000000, 999999999))
        org.tva = f"FR {random.randint(10, 99)} {org.siren}"
        org.tel_standard = self.person_faker.telephone()
        org.taille_orga = random_taille_orga()
        org.karma = random.randint(1, 10)
        fake_geoloc(org)

    def _set_images(self, org: Organisation) -> None:
        """Set logo and cover images for organization."""
        idx = random.randint(1, 14)
        logo_content = Path(f"src/app/static/tmp/logos/{idx}.png").read_bytes()
        org.logo_image = create_file_object(
            content=squared(logo_content),
            original_filename=f"logo_{idx}.png",
            content_type="image/png",
        )
        cover_content = urllib.request.urlopen(random.choice(COVER_IMAGES)).read()  # noqa: S310
        org.cover_image = create_file_object(
            content=resized(cover_content),
            original_filename="cover.jpg",
            content_type="image/jpeg",
        )

    def _set_agency_specific_info(self, org: Organisation) -> None:
        """Set agency-specific information if org is an agency."""
        if org.type != OrganisationTypeEnum.AGENCY:
            return

        org.agree_cppap = random.random() < 0.5
        match random.randint(0, 3):
            case 0:
                org.membre_sapi = True
            case 1:
                org.membre_satev = True
            case 2:
                org.membre_saphir = True

    def _set_business_wall_type(self, org: Organisation) -> None:
        """Set business wall subscription type based on organization type."""
        match org.type:
            case OrganisationTypeEnum.AUTO:
                pass
            case OrganisationTypeEnum.MEDIA:
                org.bw_type = BWTypeEnum.MEDIA  # type: ignore[assignment]
            case OrganisationTypeEnum.AGENCY:
                org.bw_type = BWTypeEnum.AGENCY  # type: ignore[assignment]
            case OrganisationTypeEnum.COM:
                org.bw_type = BWTypeEnum.COM  # type: ignore[assignment]
            case OrganisationTypeEnum.OTHER:
                org.bw_type = random.choice(  # type: ignore[assignment]
                    (
                        BWTypeEnum.CORPORATE,
                        BWTypeEnum.PRESSUNION,
                        BWTypeEnum.ORGANISATION,
                        BWTypeEnum.TRANSFORMER,
                        BWTypeEnum.ACADEMICS,
                    )
                )


def fake_agency_url():
    lines = Path("bootstrap_data/sites-web.txt").read_text().split("\n")
    lines = [line for line in lines if line]
    return random.choice(lines)
