# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import g
from flask_super.decorators import service


@service
class AuthService:
    def get_user(self):
        return g.user
