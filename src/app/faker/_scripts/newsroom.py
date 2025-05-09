# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import abc
import functools
import random
from typing import Any

from faker import Faker
from flask_super.registry import register
from loguru import logger
from svcs.flask import container

import app.settings.vocabularies as voc
from app.enums import OrganisationTypeEnum, RoleEnum
from app.faker._constants import POST_IMAGES
from app.faker._scripts.base import FakerScript
from app.flask.extensions import db
from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.models.repositories import OrganisationRepository, UserRepository
from app.modules.wip.models import (
    Article,
    AvisEnquete,
    Commande,
    ContactAvisEnquete,
    Sujet,
)

faker = Faker("fr_FR")

MAX_COUNT = 10


@functools.lru_cache
def get_medias():
    media_type = OrganisationTypeEnum.MEDIA
    org_repo = container.get(OrganisationRepository)
    return org_repo.list(type=media_type)


@functools.lru_cache
def get_journalists():
    user_repo = container.get(UserRepository)
    all_users = user_repo.list()
    result = [user for user in all_users if user.has_role(RoleEnum.PRESS_MEDIA)]
    assert result
    return result


@functools.lru_cache
def get_experts():
    user_repo = container.get(UserRepository)
    all_users = user_repo.list()
    result = [user for user in all_users if user.has_role(RoleEnum.EXPERT)]
    assert result
    return result


class BaseScript(FakerScript, abc.ABC):
    def generate(self) -> None:
        count = 0
        for user in get_journalists():
            count += self.make_multiple(user)
        logger.info("Generated {count} {name}", count=count, name=self.name)

    def make_multiple(self, user: User) -> int:
        count = random.randint(1, MAX_COUNT)
        for _i in range(count):
            obj = self.make_one(user)
            db.session.add(obj)
        return count

    @abc.abstractmethod
    def make_one(self, user: User) -> Any:
        raise NotImplementedError

    def add_metadata(self, obj) -> None:
        obj.genre = random.choice(voc.get_genres())
        obj.topic = random.choice(voc.get_topics())
        obj.section = random.choice(voc.get_sections())
        obj.sector = random.choice(voc.get_news_sectors())


@register
class SujetsFakerScript(BaseScript):
    name = "sujets"
    model_class = Sujet

    def make_one(self, user: User) -> Sujet:
        obj = Sujet(owner_id=user.id)
        obj.titre = faker.sentence()
        obj.brief = faker.text()
        obj.description = faker.text()
        obj.media = random.choice(get_medias())
        obj.commanditaire_id = random.choice(get_journalists()).id

        self.add_metadata(obj)

        obj.date_limite_validite = faker.date_time_between(
            start_date="+1d", end_date="+1y"
        )
        obj.date_parution_prevue = faker.date_time_between(
            start_date=obj.date_limite_validite, end_date="+1y"
        )
        return obj


@register
class CommandesFakerScript(BaseScript):
    name = "commandes"
    model_class = Commande

    def make_one(self, user: User) -> Sujet:
        obj = Commande(owner_id=user.id)
        obj.titre = faker.sentence()
        obj.brief = faker.text()
        obj.description = faker.text()
        obj.media = random.choice(get_medias())
        obj.commanditaire_id = random.choice(get_journalists()).id

        self.add_metadata(obj)

        obj.date_limite_validite = faker.date_time_between(
            start_date="+1d", end_date="+10d"
        )
        obj.date_bouclage = faker.date_time_between(
            start_date=obj.date_limite_validite, end_date="+10d"
        )
        obj.date_parution_prevue = faker.date_time_between(
            start_date=obj.date_bouclage, end_date="+10d"
        )
        obj.date_paiement = faker.date_time_between(
            start_date=obj.date_bouclage, end_date="+60d"
        )
        return obj


@register
class AvisEnqueteFakerScript(BaseScript):
    name = "avis-enquetes"
    model_class = AvisEnquete

    def make_one(self, user: User) -> AvisEnquete:
        obj = AvisEnquete(owner=user)

        obj.titre = faker.sentence()
        obj.brief = faker.text()
        obj.description = faker.text()
        obj.media = random.choice(get_medias())
        obj.commanditaire_id = random.choice(get_journalists()).id

        self.add_metadata(obj)

        obj.status = random.choice(list(PublicationStatus))

        obj.content = faker.text(5)

        # article.subheader = faker(2)
        obj.summary = " ".join(faker.sentences(3))
        obj.image_url = random.choice(POST_IMAGES)

        obj.published_at = faker.date_time_between(start_date="-1y", end_date="-1d")
        obj.created_at = obj.published_at

        obj.date_debut_enquete = faker.date_time_between(
            start_date="-3d", end_date="+5d"
        )
        obj.date_fin_enquete = faker.date_time_between(
            start_date=obj.date_debut_enquete, end_date="+10d"
        )
        obj.date_bouclage = faker.date_time_between(
            start_date=obj.date_fin_enquete, end_date="+10d"
        )
        obj.date_parution_prevue = faker.date_time_between(
            start_date=obj.date_bouclage, end_date="+10d"
        )

        self.make_contacts(obj)

        return obj

    def make_contacts(self, avis_enquete: AvisEnquete) -> None:
        experts = get_experts()
        assert experts
        for expert in experts:
            contact = ContactAvisEnquete(
                avis_enquete=avis_enquete,
                journaliste=avis_enquete.owner,
                expert=expert,
            )
            db.session.add(contact)
        db.session.commit()


@register
class ArticlesFakerScript(BaseScript):
    name = "articles"
    model_class = Article

    def make_one(self, user: User) -> Article:
        obj = Article(owner_id=user.id)

        obj.titre = faker.sentence()
        obj.description = faker.text()
        obj.media = random.choice(get_medias())
        obj.commanditaire_id = random.choice(get_journalists()).id

        self.add_metadata(obj)

        obj.status = random.choice(
            [
                PublicationStatus.DRAFT,
                PublicationStatus.PUBLIC,
                PublicationStatus.ARCHIVED,
            ]
        )

        obj.content = faker.text(5)

        # article.subheader = faker(2)
        obj.summary = " ".join(faker.sentences(3))
        obj.image_url = random.choice(POST_IMAGES)

        obj.published_at = faker.date_time_between(start_date="-1y", end_date="-1d")
        obj.created_at = obj.published_at

        obj.date_parution_prevue = faker.date_time_between(
            start_date=obj.published_at, end_date="+1y"
        )
        obj.date_publication_aip24 = faker.date_time_between(
            start_date=obj.published_at, end_date="+1y"
        )
        obj.date_paiement = faker.date_time_between(
            start_date=obj.published_at, end_date="+1y"
        )

        return obj
