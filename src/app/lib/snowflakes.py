# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import time
from os import getpid

from attr import define, field, mutable


@define(order=True, hash=True)
class Snowflake:
    """Snowflake object used to handle snowflakes and get metadata from them.

    :param epoch: The time to offset the epoch with when handling
        timestamp related values.
    :param _flake: The generated snowflake value
    """

    epoch: int
    _flake: int

    def __int__(self) -> int:
        return self._flake

    def __str__(self):
        return str(self._flake)

    @property
    def timestamp(self) -> float:
        """Timestamp of snowflake creation localized to the Unix Epoch :return:

        Timestamp localized to 1970/1/1.
        """
        # bits 22 and onward encode timestamp - epoch
        epochtime = self._flake >> 22

        # since the epochtime is the time *since* the epoch
        # the unix timestamp will be the time *plus* the epoch
        timestamp = epochtime + self.epoch

        # convert it back to seconds as that is how we handle other time-based values
        # around snowflakes.
        return timestamp / 1000

    @property
    def generation(self) -> int:
        return self._flake >> 0 & 0b111111111111

    @property
    def process_id(self) -> int:
        return self._flake >> 12 & 0b11111

    @property
    def worker_id(self) -> int:
        return self._flake >> 17 & 0b11111


@mutable
class Counter:
    value: int = 0

    def increment(self) -> None:
        self.value += 1


@define
class SnowflakeGenerator:
    epoch: int = field(default=0)
    process_id: int = field(factory=getpid)
    worker_id: int = field(default=0)
    _count: Counter = field(factory=Counter)

    def generate(self, timestamp: int | None = None) -> Snowflake:
        if timestamp is None:
            timestamp = int(time.time() * 1000)

        ep = timestamp - self.epoch

        sflake = ep << 22

        sflake |= (self.worker_id % 32) << 17
        sflake |= (self.process_id % 32) << 12
        sflake |= self._count.value % 4096

        self._count.increment()

        return Snowflake(self.epoch, sflake)

    def generate_as_int(self, timestamp: None = None) -> int:
        return int(self.generate(timestamp))
