# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import functools
import random

from faker import Faker
from flask_super.registry import register
from loguru import logger
from svcs.flask import container

from app.faker._scripts.base import FakerScript
from app.models.auth import RoleEnum, User
from app.models.repositories import UserRepository
from app.services.notifications import Notification, NotificationService

faker = Faker("fr_FR")

MAX_COUNT = 10


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


@register
class NotificationFakerScript(FakerScript):
    name = "notifications"
    model_class = Notification

    def generate(self) -> None:
        count = 0
        for user in get_journalists() + get_experts():
            count += self.make_notifications(user)
        logger.info("Generated {count} {name}", count=count, name=self.name)

    def make_notifications(self, user: User) -> int:
        notification_service = container.get(NotificationService)

        count = random.randint(1, MAX_COUNT)
        for _i in range(count):
            message = faker.text()
            notification_service.post(user, message)
        return count
