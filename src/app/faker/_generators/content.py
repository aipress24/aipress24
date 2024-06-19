# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import json
import random
from pathlib import Path

import app.settings.vocabularies as voc
from app.faker._constants import LOCATION, POST_CATEGORIES, POST_IMAGES
from app.flask.extensions import db
from app.models.content import PressRelease
from app.models.content.multimedia import Image
from app.models.content.textual import Article
from app.models.lifecycle import PublicationStatus
from app.services.roles import Role, has_role
from app.services.tagging import add_tag

from .base import BaseGenerator
from .util import random_wikinews_article


class ArticleGenerator(BaseGenerator):
    def make_obj(self) -> Article:
        users = self.repository["users"]
        orgs = self.repository["organisations"]

        journalists = [u for u in users if has_role(u, Role.PRESS_MEDIA)]

        article = Article()

        article.status = random.choice(list(PublicationStatus))

        wikinews_d = random_wikinews_article()
        article.title = wikinews_d["title"]
        article.content = wikinews_d["html"]
        categories = wikinews_d["categories"]

        article.subheader = self.text_faker.text(2)
        article.summary = self.text_faker.text(random.randint(1, 2))
        # article.image_url = random.choice(POST_IMAGES)

        article.owner_id = random.choice(journalists).id

        # Generate metadata
        article.genre = random.choice(voc.get_genres())
        article.topic = random.choice(voc.get_topics())
        article.section = random.choice(voc.get_sections())
        article.sector = random.choice(voc.get_sectors())

        article.published_at = self.generate_date()
        article.created_at = article.published_at
        article.publisher = random.choice(orgs)

        db.session.add(article)
        db.session.flush()

        for category in categories:
            tag = add_tag(article, category)
            db.session.add(tag)

        return article


class PhotoGenerator(BaseGenerator):
    def make_obj(self) -> Image:
        users = self.repository["users"]
        orgs = self.repository["organisations"]
        journalists = [u for u in users if has_role(u, Role.PRESS_MEDIA)]

        photo = Image()
        photo.title = self.generate_short_title()
        photo.owner_id = random.choice(journalists).id
        photo.subheader = self.text_faker.text(2)
        photo.image_url = random.choice(POST_IMAGES)
        photo.category = random.choice(POST_CATEGORIES)
        photo.content = self.generate_html()
        photo.published_at = self.generate_date()
        photo.created_at = photo.published_at
        photo.publisher = random.choice(orgs)
        return photo


def random_press_release() -> dict[str, str]:
    file_list = list(Path("data/pr").glob("*.json"))
    with random.choice(file_list).open() as fd:
        return json.load(fd)


class PressReleaseGenerator(BaseGenerator):
    def make_obj(self) -> PressRelease:
        users = self.repository["users"]
        orgs = self.repository["organisations"]

        press_release = PressRelease()
        press_release.owner_id = random.choice(users).id

        d = random_press_release()
        press_release.title = d["title"]
        press_release.content = d["html"]

        # Was:
        # press_release.title = d.title

        press_release.summary = self.text_faker.text(random.randint(1, 2))
        press_release.location = random.choice(LOCATION)

        press_release.status = random.choice(["draft", "public"])
        press_release.category = random.choice(POST_CATEGORIES)
        press_release.sector = random.choice(voc.get_sectors())
        press_release.image_url = random.choice(POST_IMAGES)

        press_release.published_at = self.generate_date()
        press_release.created_at = press_release.published_at
        press_release.publisher = random.choice(orgs)

        return press_release
