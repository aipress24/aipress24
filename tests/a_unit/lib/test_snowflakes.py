# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import time

from app.lib import snowflakes


def test_flakes_are_unique() -> None:
    generator = snowflakes.SnowflakeGenerator()
    count = 10000
    flakes = {generator.generate() for _ in range(count)}
    assert len(flakes) == count


def test_flakes_attributes() -> None:
    flake = snowflakes.Snowflake(0, 0)
    assert str(int(flake)) == str(flake)
    assert 0 <= flake.process_id <= 0b11111
    assert 0 <= flake.worker_id <= 0b11111
    assert 0 <= flake.generation <= 0b111111111111


def test_snowflake_timestamp() -> None:
    """Test Snowflake timestamp property."""
    epoch = 1640000000000  # Some epoch in milliseconds
    generator = snowflakes.SnowflakeGenerator(epoch=epoch)

    # Generate a snowflake with a specific timestamp
    timestamp_ms = int(time.time() * 1000)
    flake = generator.generate(timestamp=timestamp_ms)

    # The timestamp property should return the time in seconds
    assert isinstance(flake.timestamp, float)
    # Should be close to current time
    current_time = time.time()
    assert abs(flake.timestamp - current_time) < 1  # Within 1 second


def test_snowflake_timestamp_calculation() -> None:
    """Test Snowflake timestamp calculation with known values."""
    epoch = 1000000000000  # 1 billion seconds in ms
    # Create a snowflake directly with known values
    # bits 22 and onward encode timestamp - epoch
    timestamp_offset = 5000  # 5 seconds in ms
    flake_value = timestamp_offset << 22
    flake = snowflakes.Snowflake(epoch, flake_value)

    # Expected: (timestamp_offset + epoch) / 1000
    expected = (timestamp_offset + epoch) / 1000
    assert flake.timestamp == expected


def test_generate_as_int() -> None:
    """Test generate_as_int method."""
    generator = snowflakes.SnowflakeGenerator()
    result = generator.generate_as_int()

    assert isinstance(result, int)
    assert result > 0
