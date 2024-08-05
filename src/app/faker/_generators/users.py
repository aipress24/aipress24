# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import random
import urllib.request

from mimesis import Person
from mimesis.enums import Gender

from app.faker._constants import COVER_IMAGES
from app.faker._geo import fake_geoloc
from app.flask.extensions import db, security
from app.models.auth import CommunityEnum, KYCProfile, User
from app.modules.kyc.populate_profile import populate_json_field
from app.modules.kyc.survey_model import get_survey_profile, get_survey_profile_ids
from app.modules.wallet.models import IndividualWallet
from app.settings.vocabularies.user import USER_STATUS

from .base import BaseGenerator

GENDERS = {
    "M": Gender.MALE,
    "F": Gender.FEMALE,
}


def random_profile_id() -> str:
    return random.choice(get_survey_profile_ids())


class UserGenerator(BaseGenerator):
    users: list[User] = []

    def __post_init__(self) -> None:
        super().__post_init__()
        self.person_faker = Person(self.locale)

    @staticmethod
    def _load_photo_profil(user: User) -> None:
        try:
            user.photo = urllib.request.urlopen(  # noqa: S310
                user.profile_image_url
            ).read()
            user.photo_filename = user.profile_image_url
        except Exception as e:
            print(e)

    def make_obj(self) -> User:
        datastore = security.datastore
        user: User = datastore.create_user()

        self.counter += 1

        user.gender = random.choice(["M", "F"])
        gender = GENDERS[user.gender]
        user.first_name = self.person_faker.first_name(gender)
        user.last_name = self.person_faker.last_name(gender)
        user.presentation = self.generate_text(300)

        user.email = self.person_faker.email(unique=True)
        user.telephone = self.person_faker.telephone()

        user.tel_mobile = self.person_faker.telephone()

        survey_profile = get_survey_profile(random_profile_id())

        profile = KYCProfile(
            profile_id=survey_profile.id,
            profile_label=survey_profile.label,
            profile_community=survey_profile.community,
            info_professionnelle=populate_json_field("info_professionnelle", {}),
            match_making=populate_json_field("match_making", {}),
            hobbies=populate_json_field("hobbies", {}),
            business_wall=populate_json_field("business_wall", {}),
        )
        user.profile = profile

        # job_titles = ROLES + ROLES + ROLES + [faker.job() for i in range(1, 100)]
        # user.job_title = random.choice(job_titles)
        user.job_title = survey_profile.label

        # user.job_description = self.generate_html(1, 4)
        user.job_description = ""
        # bio is now "experiences"
        # user.bio = self.generate_html(1, 4)
        bio = self.generate_text(1500)
        user.bio = bio
        user.profile.match_making["experiences"] = bio

        # education is now "formations""
        # user.education = self.generate_html(0, 4)
        education = self.generate_text(1500)
        user.education = education
        user.profile.match_making["formations"] = education

        hobbies = self.generate_text(1500)
        user.hobbies = hobbies
        user.profile.hobbies["hobbies"] = hobbies

        user.profile_image_url = self.get_profile_image(user)
        self._load_photo_profil(user)
        user.cover_image_url = random.choice(COVER_IMAGES)

        user.status = random.choice(USER_STATUS)
        user.karma = random.randint(0, 100)
        user.mojo = random.randint(0, 1000)

        user.password = ""

        user.geoloc = fake_geoloc()

        # fixme: check what is this field
        user.community = random.choice(list(CommunityEnum))
        # user.community = survey_profile.community

        self.make_wallet(user)

        self.users += [user]
        return user

    # def make_username(self) -> str:
    #     while True:
    #         username = self.person_faker.username(drange=(0, 1000))
    #         if username not in {u.username for u in self.users}:
    #             break
    #     return username

    def make_wallet(self, user: User) -> None:
        balance = random.randint(0, 1000)
        wallet = IndividualWallet(user=user, balance=balance)
        db.session.add(wallet)
