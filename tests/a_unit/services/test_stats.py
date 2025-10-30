# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import arrow
from flask_sqlalchemy import SQLAlchemy

from app.models.auth import User
from app.models.content import BaseContent
from app.services.stats._metrics import (
    ActiveOrganisations,
    ActiveUsers,
    CountContents,
    Metric,
)
from app.services.stats._models import StatsRecord


def test_create_record(db: SQLAlchemy) -> None:
    record = StatsRecord(
        date=arrow.now().date(),
        key="test",
        value=1,
    )
    db.session.add(record)
    db.session.flush()


class TestMetricBaseClass:
    """Test suite for Metric base class."""

    def test_metric_default_compute(self, db: SQLAlchemy) -> None:
        """Test that base Metric.compute() returns 0."""
        metric = Metric()
        start = arrow.now()
        end = arrow.now()
        result = metric.compute(start, end)
        assert result == 0


class TestActiveUsers:
    """Test suite for ActiveUsers metric."""

    def test_active_users_id(self) -> None:
        """Test ActiveUsers has correct id."""
        metric = ActiveUsers()
        assert metric.id == "active_users"

    def test_active_users_compute_default(self, db: SQLAlchemy) -> None:
        """Test ActiveUsers uses default compute (returns 0)."""
        metric = ActiveUsers()
        start = arrow.now()
        end = arrow.now()
        result = metric.compute(start, end)
        assert result == 0


class TestActiveOrganisations:
    """Test suite for ActiveOrganisations metric."""

    def test_active_organisations_id(self) -> None:
        """Test ActiveOrganisations has correct id."""
        metric = ActiveOrganisations()
        assert metric.id == "active_organisations"

    def test_active_organisations_compute_default(self, db: SQLAlchemy) -> None:
        """Test ActiveOrganisations uses default compute (returns 0)."""
        metric = ActiveOrganisations()
        start = arrow.now()
        end = arrow.now()
        result = metric.compute(start, end)
        assert result == 0


class TestCountContents:
    """Test suite for CountContents metric."""

    def test_count_contents_id(self) -> None:
        """Test CountContents has correct id."""
        metric = CountContents()
        assert metric.id == "count_contents"

    def test_count_contents_no_content(self, db: SQLAlchemy) -> None:
        """Test counting when no contents exist."""
        metric = CountContents()
        start = arrow.now().shift(days=-7)
        end = arrow.now()
        result = metric.compute(start, end)
        assert result == 0.0

    def test_count_contents_one_content(self, db: SQLAlchemy) -> None:
        """Test counting with one content in date range."""
        user = User(email="test@example.com")
        db.session.add(user)
        db.session.flush()

        # Create content with specific timestamp
        now = arrow.now()
        content = BaseContent(owner=user, created_at=now.datetime)
        db.session.add(content)
        db.session.flush()

        metric = CountContents()
        start = now.shift(hours=-1)
        end = now.shift(hours=1)
        result = metric.compute(start, end)
        assert result == 1.0

    def test_count_contents_multiple_contents(self, db: SQLAlchemy) -> None:
        """Test counting with multiple contents in date range."""
        user = User(email="test@example.com")
        db.session.add(user)
        db.session.flush()

        # Create multiple contents
        now = arrow.now()
        for i in range(5):
            content = BaseContent(owner=user, created_at=now.shift(hours=-i).datetime)
            db.session.add(content)
        db.session.flush()

        metric = CountContents()
        start = now.shift(hours=-10)
        end = now.shift(hours=1)
        result = metric.compute(start, end)
        assert result == 5.0

    def test_count_contents_outside_date_range(self, db: SQLAlchemy) -> None:
        """Test that contents outside date range are not counted."""
        user = User(email="test@example.com")
        db.session.add(user)
        db.session.flush()

        # Create content outside range
        old_date = arrow.now().shift(days=-30)
        content = BaseContent(owner=user, created_at=old_date.datetime)
        db.session.add(content)
        db.session.flush()

        metric = CountContents()
        start = arrow.now().shift(days=-7)
        end = arrow.now()
        result = metric.compute(start, end)
        assert result == 0.0

    def test_count_contents_boundary_dates(self, db: SQLAlchemy) -> None:
        """Test that contents on boundary dates are counted correctly."""
        user = User(email="test@example.com")
        db.session.add(user)
        db.session.flush()

        # Create contents on start and end dates
        start = arrow.now().shift(days=-7)
        end = arrow.now()

        content1 = BaseContent(owner=user, created_at=start.datetime)
        content2 = BaseContent(owner=user, created_at=end.datetime)
        db.session.add_all([content1, content2])
        db.session.flush()

        metric = CountContents()
        result = metric.compute(start, end)
        assert result == 2.0

    def test_count_contents_with_arrow_objects(self, db: SQLAlchemy) -> None:
        """Test compute with Arrow objects as input."""
        user = User(email="test@example.com")
        db.session.add(user)
        db.session.flush()

        now = arrow.now()
        content = BaseContent(owner=user, created_at=now.datetime)
        db.session.add(content)
        db.session.flush()

        metric = CountContents()
        # Pass Arrow objects directly
        start = arrow.get(now.shift(hours=-1))
        end = arrow.get(now.shift(hours=1))
        result = metric.compute(start, end)
        assert result == 1.0
