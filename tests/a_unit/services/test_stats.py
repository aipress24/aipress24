# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import arrow
from flask_sqlalchemy import SQLAlchemy

from app.models.auth import User
from app.models.content import BaseContent
from app.services.stats._compute import DURATIONS, update_stats
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


class TestUpdateStats:
    """Test suite for update_stats function."""

    def test_update_stats_creates_records(self, db: SQLAlchemy) -> None:
        """Test that update_stats creates StatsRecord entries."""
        # Run update_stats with a specific date
        test_date = "2024-01-15"
        update_stats(date=test_date)

        # Check that records were created
        records = db.session.query(StatsRecord).all()
        # Should have records for each metric × each duration (day, week, month)
        assert len(records) > 0

    def test_update_stats_uses_current_date_by_default(self, db: SQLAlchemy) -> None:
        """Test that update_stats uses current date when none provided."""
        update_stats()

        # Should have created some records
        records = db.session.query(StatsRecord).all()
        assert len(records) > 0

    def test_update_stats_creates_records_for_all_durations(
        self, db: SQLAlchemy
    ) -> None:
        """Test that update_stats creates records for day, week, month."""
        update_stats(date="2024-01-15")

        # Get distinct durations from created records
        records = db.session.query(StatsRecord).all()
        durations = {r.duration for r in records}

        # Should have records for each duration type
        expected_durations = {d[0] for d in DURATIONS}
        assert durations == expected_durations

    def test_update_stats_stores_metric_values(self, db: SQLAlchemy) -> None:
        """Test that update_stats stores computed metric values."""
        update_stats(date="2024-01-15")

        # Check that records have expected keys
        records = db.session.query(StatsRecord).all()
        keys = {r.key for r in records}

        # Should have records for registered metrics
        assert "count_contents" in keys
        assert "active_users" in keys
        assert "active_organisations" in keys


class TestDurationsConstant:
    """Test suite for DURATIONS constant."""

    def test_durations_has_expected_keys(self) -> None:
        """Test that DURATIONS contains expected duration types."""
        duration_names = [d[0] for d in DURATIONS]
        assert "day" in duration_names
        assert "week" in duration_names
        assert "month" in duration_names

    def test_durations_has_valid_shifts(self) -> None:
        """Test that each duration has a valid shift dict."""
        for name, shift in DURATIONS:
            assert isinstance(shift, dict)
            assert len(shift) == 1  # Each should have one key
