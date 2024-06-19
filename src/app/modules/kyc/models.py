# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from sqlalchemy.orm import mapped_column
from sqlalchemy_utils import JSONType

from app.models.base import Base
from app.models.mixins import IdMixin


class MembershipApplication(IdMixin, Base):
    __tablename__ = "kyc_membership_application"

    data = mapped_column(JSONType)
