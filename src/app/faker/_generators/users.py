# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import random
import urllib.request

from mimesis import Person
from mimesis.enums import Gender

from app.faker._constants import COVER_IMAGES, ROLES
from app.faker._geo import fake_geoloc
from app.flask.extensions import db, security
from app.models.auth import CommunityEnum, User
from app.modules.wallet.models import IndividualWallet
from app.settings.vocabularies.user import USER_STATUS

from .base import BaseGenerator, faker

GENDERS = {
    "M": Gender.MALE,
    "F": Gender.FEMALE,
}


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

        user.email = self.person_faker.email(unique=True)
        user.telephone = self.person_faker.telephone()

        user.tel_mobile = self.person_faker.telephone()

        job_titles = ROLES + ROLES + ROLES + [faker.job() for i in range(1, 100)]
        user.job_title = random.choice(job_titles)

        user.job_description = self.generate_html(1, 4)
        user.bio = self.generate_html(1, 4)
        user.education = self.generate_html(0, 4)
        user.hobbies = self.generate_html(0, 3)

        user.profile_image_url = self.get_profile_image(user)
        self._load_photo_profil(user)
        user.cover_image_url = random.choice(COVER_IMAGES)

        user.status = random.choice(USER_STATUS)
        user.karma = random.randint(0, 100)
        user.mojo = random.randint(0, 1000)

        user.password = ""

        user.geoloc = fake_geoloc()

        user.community = random.choice(list(CommunityEnum))

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
