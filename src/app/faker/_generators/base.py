# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import random
from abc import ABC
from dataclasses import dataclass
from random import randint
from typing import Any

import arrow
from faker import Faker
from mimesis import Text
from mimesis.enums import Locale

faker = Faker("fr_FR")


@dataclass
class BaseGenerator(ABC):
    repository: dict[str, list[Any]]
    locale: Locale
    counter: int = 0

    def __post_init__(self):
        self.text_faker = Text(self.locale)
        self.objects = set()

    def make_obj(self):
        raise NotImplementedError

    def make_objects(self, count):
        result = []
        for _i in range(count):
            obj = self.make_obj()
            self.objects.add(obj)
            result.append(obj)
        return result

    def generate_short_title(self):
        while True:
            title = self.text_faker.title()
            if len(title) < 150:
                return title

    def generate_html(self, min_sentences=5, max_sentences=15):
        num_paragraphs = random.randint(min_sentences, max_sentences)
        paragraphs = [self.generate_html_p() for i in range(num_paragraphs)]
        return "\n".join(paragraphs)

    def generate_html_p(self) -> str:
        num_sentences = random.randint(1, 5)
        return f"<p>{self.text_faker.text(num_sentences)}</p>\n"

    def get_profile_image(self, user) -> str:
        if user.gender == "M":
            k1 = "men"
        else:
            k1 = "women"
        k2 = randint(0, 99)
        return f"https://randomuser.me/api/portraits/{k1}/{k2}.jpg"

    def generate_date(self, past=True, future=False):
        """Generate a random date, by default in the past."""
        match past, future:
            case [True, False]:
                return arrow.now().shift(days=randint(-365, 0), hours=randint(-24, 0))
            case [False, True]:
                return arrow.now().shift(days=randint(0, 365), hours=randint(0, 24))
            case [True, True]:
                return arrow.now().shift(
                    days=randint(-365, 365), hours=randint(-24, 24)
                )
            case _:
                raise ValueError(f"Illegal arguments: {(past, future)}")
