# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the `@job()` and `@crontab(...)` decorators.

Both decorators wrap the target function in a `LazyActor` and stash
it on a module-level `_actor_registry` set. At app startup,
`register_regular_jobs()` / `register_cron_jobs()` walk that set and
bind every actor to the active broker.

These tests pin the decorator contracts independently from the
broker — i.e. without spinning up a `StubBroker` (covered by
`tests/a_unit/dramatiq/test_lazy_actor.py`)."""

from __future__ import annotations

import importlib

import pytest

from app.dramatiq.lazy_actor import LazyActor

# `app.dramatiq.__init__` does `from .job import job`, which shadows
# the submodule access `app.dramatiq.job` with the function. Force
# the submodule via importlib so we can reach `_actor_registry`.
job_module = importlib.import_module("app.dramatiq.job")
scheduler_module = importlib.import_module("app.dramatiq.scheduler")


@pytest.fixture
def clean_job_registry():
    """Snapshot + restore the job registry so we don't pollute the
    real one (which already has every `@job()` from `app/actors/`
    registered at module load)."""
    snapshot = set(job_module._actor_registry)
    job_module._actor_registry.clear()
    try:
        yield job_module._actor_registry
    finally:
        job_module._actor_registry.clear()
        job_module._actor_registry.update(snapshot)


@pytest.fixture
def clean_crontab_registry():
    snapshot = set(scheduler_module._actor_registry)
    scheduler_module._actor_registry.clear()
    try:
        yield scheduler_module._actor_registry
    finally:
        scheduler_module._actor_registry.clear()
        scheduler_module._actor_registry.update(snapshot)


class TestJobDecorator:
    def test_returns_a_lazy_actor(self, clean_job_registry):
        @job_module.job()
        def _my_actor() -> str:
            return "ok"

        assert isinstance(_my_actor, LazyActor)
        assert _my_actor() == "ok"

    def test_registers_in_module_registry(self, clean_job_registry):
        @job_module.job()
        def _another_actor() -> None:
            pass

        assert _another_actor in clean_job_registry

    def test_multiple_decorations_all_registered(self, clean_job_registry):
        @job_module.job()
        def _actor_a() -> None:
            pass

        @job_module.job()
        def _actor_b() -> None:
            pass

        assert {_actor_a, _actor_b} <= clean_job_registry


class TestCrontabDecorator:
    def test_returns_a_lazy_actor_with_schedule(self, clean_crontab_registry):
        @scheduler_module.crontab("*/5 * * * *")
        def _my_cron() -> None:
            pass

        assert isinstance(_my_cron, LazyActor)
        # The cron expression is stored on the LazyActor for the
        # scheduler to pick up at startup.
        assert _my_cron.crontab == "*/5 * * * *"

    def test_registers_in_cron_registry(self, clean_crontab_registry):
        @scheduler_module.crontab("0 0 * * *")
        def _daily_cron() -> None:
            pass

        assert _daily_cron in clean_crontab_registry

    def test_cron_registry_is_separate_from_job_registry(
        self, clean_job_registry, clean_crontab_registry
    ):
        """A `@crontab(...)` actor goes into the scheduler's set, not
        the regular-jobs one. Mixing them up would cause the
        scheduler to fire one-off jobs as crons and vice-versa."""

        @scheduler_module.crontab("0 0 * * *")
        def _cron_only() -> None:
            pass

        @job_module.job()
        def _job_only() -> None:
            pass

        assert _cron_only in clean_crontab_registry
        assert _cron_only not in clean_job_registry
        assert _job_only in clean_job_registry
        assert _job_only not in clean_crontab_registry
