# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `flask queue worker`.

The command builds an argv and `exec`s into dramatiq, so the only
thing to pin is that argv. It must resolve dramatiq through
`sys.executable -m` and never through a PATH lookup: process
supervisors (Piku, Hop3, honcho) invoke `.venv/bin/flask` by path
without activating the venv, so `dramatiq` is not on PATH there."""

from __future__ import annotations

import os
import sys

import pytest

from app.dramatiq.cli import WORKER_ENTRY, worker


@pytest.fixture
def argv(monkeypatch) -> list:
    """Capture the argv `worker` execs into, instead of execing."""
    captured = []
    monkeypatch.setattr(os, "execv", lambda path, args: captured.extend([path, args]))
    return captured


def test_worker_execs_the_running_interpreter(argv) -> None:
    worker.callback(verbose=0, processes=1, threads=1, queues=None)

    path, args = argv
    assert path == sys.executable
    assert args[:4] == [sys.executable, "-m", "dramatiq", WORKER_ENTRY]


def test_worker_passes_options_through(argv) -> None:
    worker.callback(verbose=2, processes=2, threads=4, queues="foo,bar")

    _, args = argv
    assert args[4:] == [
        "--processes",
        "2",
        "--threads",
        "4",
        "--queues",
        "foo",
        "bar",
        "-v",
        "-v",
    ]
