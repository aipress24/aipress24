"""BANO (Base Adresse Nationale Ouverte) data import jobs."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import json
from pathlib import Path
from random import choice

import rich
from flask_super.registry import register
from sqlalchemy import select

from app.flask.extensions import db
from app.flask.lib.jobs import Job
from app.flask.sqla import get_multi
from app.models.auth import User
from app.models.mixins import Addressable
from app.modules.events.models import EventPost
from app.modules.wire.models import PressReleasePost

CLASSES_TO_FIX = [
    EventPost,
    PressReleasePost,
    # EditorialContent,
    User,
    # Organisation,
]


@register
class BanoJob(Job):
    name = "bano"
    description = "Generate fake adresses from BANO"

    streets: list[dict]

    def run(self, *args) -> None:
        self.streets = self.get_streets()
        for cls in CLASSES_TO_FIX:
            self.fix_class(cls)
        db.session.commit()

    def get_streets(self):
        with Path("bootstrap_data/bano-streets-sample.json").open() as fd:
            return json.load(fd)

    def fix_class(self, cls: type[Addressable]) -> None:
        stmt = select(cls)
        objs: list[Addressable] = list(get_multi(cls, stmt))
        for obj in objs:
            self.fix_obj(obj)
        rich.print(f"[green]Fixed {len(objs)} {cls.__name__}[/green]")

    def fix_obj(self, obj: Addressable) -> None:
        street = choice(self.streets)
        obj.address = street["name"]
        obj.city = street["city"]
        obj.zip_code = street["postcode"]
        obj.region = street["region"]
        obj.departement_deprecated = street["departement"]
        obj.geo_lat = street["lat"]
        obj.geo_lng = street["lon"]
