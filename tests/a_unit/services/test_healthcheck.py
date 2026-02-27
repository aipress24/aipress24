# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for services/healthcheck.py"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.services.healthcheck import healthcheck

if TYPE_CHECKING:
    from flask_sqlalchemy import SQLAlchemy


def test_healthcheck_succeeds_with_database(db: SQLAlchemy) -> None:
    """Test healthcheck succeeds when database is available."""
    # Should not raise an exception
    healthcheck()
