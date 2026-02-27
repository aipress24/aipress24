# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests for WIP performance views."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from app.modules.wip.views.performance import is_sorted
from app.services.reputation._models import ReputationRecord

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session

    from app.models.auth import User


class TestPerformancePage:
    """Tests for the performance page."""

    def test_performance_page_loads(
        self, logged_in_client: FlaskClient, test_user: User
    ):
        """Test that performance page loads successfully."""
        response = logged_in_client.get("/wip/performance")
        assert response.status_code == 200
        assert "performance" in response.data.decode().lower()

    def test_performance_page_with_empty_history(
        self, logged_in_client: FlaskClient, test_user: User
    ):
        """Test performance page renders with no reputation history."""
        response = logged_in_client.get("/wip/performance")
        assert response.status_code == 200
        # Page should still render even with empty data
        assert b"performance" in response.data.lower()

    def test_performance_page_with_history(
        self,
        logged_in_client: FlaskClient,
        test_user: User,
        db_session: Session,
    ):
        """Test performance page renders with reputation history data."""
        # Create reputation records
        records = [
            ReputationRecord(
                user_id=test_user.id,
                date=date(2024, 1, 1),
                value=50.0,
                details={},
            ),
            ReputationRecord(
                user_id=test_user.id,
                date=date(2024, 1, 15),
                value=75.0,
                details={},
            ),
            ReputationRecord(
                user_id=test_user.id,
                date=date(2024, 2, 1),
                value=80.0,
                details={},
            ),
        ]
        for record in records:
            db_session.add(record)
        db_session.commit()

        response = logged_in_client.get("/wip/performance")
        assert response.status_code == 200


class TestIsSorted:
    """Tests for the is_sorted helper function."""

    def test_empty_sequence_is_sorted(self):
        """Empty sequence is considered sorted."""
        assert is_sorted([]) is True

    def test_single_element_is_sorted(self):
        """Single element sequence is considered sorted."""
        assert is_sorted([1]) is True

    def test_sorted_sequence(self):
        """Sorted sequence returns True."""
        assert is_sorted([1, 2, 3, 4, 5]) is True

    def test_unsorted_sequence(self):
        """Unsorted sequence returns False."""
        assert is_sorted([1, 3, 2, 4, 5]) is False

    def test_sorted_with_key_function(self):
        """Sorted with key function works."""
        data = [{"x": 1}, {"x": 2}, {"x": 3}]
        assert is_sorted(data, key=lambda d: d["x"]) is True

    def test_unsorted_with_key_function(self):
        """Unsorted with key function returns False."""
        data = [{"x": 1}, {"x": 3}, {"x": 2}]
        assert is_sorted(data, key=lambda d: d["x"]) is False

    def test_equal_elements_is_sorted(self):
        """Sequence with equal elements is considered sorted."""
        assert is_sorted([1, 1, 1, 1]) is True
