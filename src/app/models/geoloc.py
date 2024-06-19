# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

# import sqlalchemy.orm

# TODO: use a relationship this class instead of subclassing Addressable?


class GeoLocation(Base):
    __tablename__ = "geo_loc"
    __table_args__ = (sa.Index("coordinate_idx", "lat", "lng"),)

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True)

    lat: Mapped[Decimal] = mapped_column(sa.DECIMAL(11, 7))
    lng: Mapped[Decimal] = mapped_column(sa.DECIMAL(11, 7))

    address: Mapped[str] = mapped_column(default="")
    city_name: Mapped[str] = mapped_column(default="")
    postal_code: Mapped[str] = mapped_column(sa.VARCHAR(30), default="")
    country_name: Mapped[str] = mapped_column(default="")
    dept_code: Mapped[str] = mapped_column(default="")

    # route = sa.Column(sa.VARCHAR(200))
    # street_number = sa.Column(sa.VARCHAR(20))
    # address = sa.Column(sa.VARCHAR(255), nullable=False)

    # country_id = sa.Column(sa.ForeignKey("geo_country.id"), nullable=False, index=True)
    # area_id = sa.Column(sa.ForeignKey("geo_area.id"), index=True)
    # department_id = sa.Column(sa.ForeignKey("geo_department.id"), index=True)
    # city_id = sa.Column(sa.ForeignKey("geo_city.id"), index=True)
    #
    # area = sa.orm.relationship("GeoArea")
    # city = sa.orm.relationship("GeoCity")
    # country = sa.orm.relationship("GeoCountry")
    # department = sa.orm.relationship("GeoDepartment")
