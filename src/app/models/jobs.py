# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""
'-----------------------------------------------------------------
'Job content
'-----------------------------------------------------------------

class JobPost {
    +rome_code string
    +location Location
    +min_salary: currency
    +max_salary: currency

    +body_html string
    +context string
    +mission string
}
JobPost -up-|> BaseContent
JobPost -- Employer

class Employer {
}
Employer -- OrganisationPage
"""

from __future__ import annotations

import datetime

import arrow
import sqlalchemy as sa
from slugify import slugify
from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .mixins import IdMixin, LifeCycleMixin, Owned
from .organisation import Organisation


class JobPost(IdMixin, LifeCycleMixin, Owned, Base):
    __tablename__ = "job_post"

    title: Mapped[str]
    slug: Mapped[str]
    description: Mapped[str]

    # Discriminators
    rome_code: Mapped[str]
    location: Mapped[str]

    #: Computed from Score, stars, views... and decay
    karma: Mapped[int] = mapped_column(default=0)

    employer_id: Mapped[int] = mapped_column(
        BigInteger,
        sa.ForeignKey(Organisation.id, onupdate="CASCADE", ondelete="CASCADE"),
    )
    employer = relationship(Organisation)

    #: Id Pôle Emploi
    pe_id: Mapped[str] = mapped_column(index=True)

    #: Extra data
    _data: Mapped[dict] = mapped_column(sa.JSON, default={})

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        if "slug" not in kwargs:
            self.slug = slugify(self.title)

    @property
    def date(self) -> datetime.date:
        return self.created_at.date()
        # date = self.created_at
        # return Date(date.year, date.month, date.day)

    @property
    def age(self) -> int:
        delta = arrow.now().date() - self.date
        return delta.days


class CV(IdMixin, LifeCycleMixin, Owned, Base):
    __tablename__ = "job_cv"

    title: Mapped[str]
    description: Mapped[str]

    rome_code: Mapped[str]
    location: Mapped[str]

    @property
    def date(self) -> datetime.date:
        return self.created_at.date()
        # created_at: Arrow = cast(Arrow, self.created_at)
        # date = self.created_at.
        # return Date(date.year, date.month, date.day)

    @property
    def age(self) -> int:
        delta = arrow.now().date() - self.date
        return delta.days
