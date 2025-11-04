# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Pytest fixtures for POC tests."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import fsspec
import pytest
from advanced_alchemy.base import UUIDAuditBase
from advanced_alchemy.types.file_object import storages
from advanced_alchemy.types.file_object.backends.fsspec import FSSpecBackend
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

if TYPE_CHECKING:
    from poc.blueprints.bw_activation_full.models import BusinessWall


@pytest.fixture(scope="session")
def file_storage_backend():
    """Configure file storage backend for testing."""
    # Create a temporary directory for file storage
    temp_dir = tempfile.mkdtemp()
    temp_path = Path(temp_dir)

    # Register the local storage backend using FSSpec
    fs = fsspec.filesystem("file")
    backend = FSSpecBackend(fs=fs, key="local", prefix=str(temp_path))
    storages.register_backend(backend)

    yield temp_path

    # Cleanup is handled automatically by tempfile


@pytest.fixture(scope="session")
def engine(file_storage_backend):
    """Create an in-memory SQLite engine for POC tests."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    return engine


@pytest.fixture(scope="session")
def tables(engine):
    """Create all POC model tables."""
    # Import models to register them with metadata
    from poc.blueprints.bw_activation_full.models import BusinessWall

    assert BusinessWall  # to avoid unused import warning

    # Create all tables
    UUIDAuditBase.metadata.create_all(engine)
    yield
    UUIDAuditBase.metadata.drop_all(engine)


@pytest.fixture
def db_session(engine, tables):
    """Create a new database session for each test."""
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def mock_user_id() -> int:
    """Return a mock user ID for testing."""
    return 1


@pytest.fixture
def mock_payer_id() -> int:
    """Return a mock payer user ID for testing."""
    return 2


@pytest.fixture
def mock_org_id() -> int:
    """Return a mock organisation ID for testing."""
    return 100


@pytest.fixture
def business_wall(db_session: Session, mock_user_id: int) -> BusinessWall:
    """Create a test BusinessWall."""
    from poc.blueprints.bw_activation_full.models import BusinessWall

    bw = BusinessWall(
        bw_type="media",
        status="draft",
        is_free=True,
        owner_id=mock_user_id,
        payer_id=mock_user_id,
    )
    db_session.add(bw)
    db_session.commit()
    return bw


@pytest.fixture
def paid_business_wall(
    db_session: Session, mock_user_id: int, mock_payer_id: int
) -> BusinessWall:
    """Create a paid BusinessWall."""
    from poc.blueprints.bw_activation_full.models import BusinessWall

    bw = BusinessWall(
        bw_type="pr",
        status="draft",
        is_free=False,
        owner_id=mock_user_id,
        payer_id=mock_payer_id,
    )
    db_session.add(bw)
    db_session.commit()
    return bw
