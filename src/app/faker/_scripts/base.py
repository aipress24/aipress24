# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import abc
from typing import Never

import click
from sqlalchemy import func, select

from app.flask.extensions import db


class FakerScript(abc.ABC):
    name: str = ""
    model_class: type | None = None

    def __init__(self) -> None:
        self.counter = 0

    @property
    def description(self) -> str:
        return f"Generate fake {self.name}"

    def run(self, delete_existing: bool = False) -> None:
        if delete_existing:
            click.secho(f"Deleting existing {self.name}...", fg="yellow")
            db.session.query(self.model_class).delete()
            db.session.flush()

        stmt = select(func.count()).select_from(self.model_class)
        count = db.session.scalar(stmt)
        if count:
            print("Skipping", self.name, "because it already exists")
            return

        self.generate()

    @abc.abstractmethod
    def generate(self) -> Never:
        raise NotImplementedError
