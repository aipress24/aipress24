# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

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
