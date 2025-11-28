# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for lib/snowflakes.py"""

from __future__ import annotations

import time

from app.lib import snowflakes


def test_flakes_are_unique() -> None:
    """Test generated flakes are unique."""
    generator = snowflakes.SnowflakeGenerator()
    count = 10000
    flakes = {generator.generate() for _ in range(count)}
    assert len(flakes) == count


def test_snowflake_attributes_and_conversions() -> None:
    """Test Snowflake attributes, int/str conversions, and bounds."""
    flake = snowflakes.Snowflake(0, 12345)

    # Conversions
    assert int(flake) == 12345
    assert str(flake) == "12345"
    assert str(int(flake)) == str(flake)

    # Attribute bounds
    assert 0 <= flake.process_id <= 0b11111
    assert 0 <= flake.worker_id <= 0b11111
    assert 0 <= flake.generation <= 0b111111111111


def test_snowflake_ordering_and_equality() -> None:
    """Test Snowflake comparison and hashing."""
    flake1 = snowflakes.Snowflake(0, 100)
    flake2 = snowflakes.Snowflake(0, 100)
    flake3 = snowflakes.Snowflake(0, 200)

    # Equality
    assert flake1 == flake2
    assert flake1 != flake3
    assert hash(flake1) == hash(flake2)

    # Ordering
    assert flake1 < flake3
    assert flake3 > flake1


def test_snowflake_timestamp() -> None:
    """Test Snowflake timestamp extraction."""
    epoch = 1640000000000
    generator = snowflakes.SnowflakeGenerator(epoch=epoch)
    timestamp_ms = int(time.time() * 1000)
    flake = generator.generate(timestamp=timestamp_ms)

    assert isinstance(flake.timestamp, float)
    assert abs(flake.timestamp - time.time()) < 1


def test_generator_with_custom_ids() -> None:
    """Test SnowflakeGenerator with custom worker and process IDs."""
    generator = snowflakes.SnowflakeGenerator(worker_id=5, process_id=10)
    flake = generator.generate()

    assert flake.worker_id == 5
    assert flake.process_id == 10 % 32


def test_generate_as_int() -> None:
    """Test generate_as_int returns integer."""
    generator = snowflakes.SnowflakeGenerator()
    result = generator.generate_as_int()

    assert isinstance(result, int)
    assert result > 0
