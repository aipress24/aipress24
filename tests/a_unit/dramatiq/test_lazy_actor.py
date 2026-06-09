# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `LazyActor`, the wrapper that decouples actor
declaration (decorator-time) from broker registration (app-startup time).

`LazyActor` ships with `dramatiq` as our core actor primitive — every
`@job()` and `@crontab(...)` in `app.actors.*` and `app.dramatiq.*`
returns one. The class was previously untested, so its contract
(callable before register, `.send()` requires register, `__getattr__`
delegates only post-register) wasn't pinned down. These tests pin it.
"""

from __future__ import annotations

import pytest
from dramatiq.brokers.stub import StubBroker

from app.dramatiq.lazy_actor import LazyActor


def _fn(x: int = 0) -> int:
    """Trivial function used as the wrapped target.

    Lives at module scope so dramatiq's actor registration (which
    needs an importable callable for serialization) doesn't choke.
    """
    return x + 1


class TestLazyActorConstruction:
    def test_stores_function(self):
        actor = LazyActor(_fn)
        assert actor.fn is _fn

    def test_crontab_defaults_to_none(self):
        actor = LazyActor(_fn)
        assert actor.crontab is None

    def test_crontab_is_pulled_out_of_kwargs(self):
        """The cron expression isn't a dramatiq option — `LazyActor`
        pops it from kwargs and stores it on `.crontab`. Anything
        else is forwarded to `dramatiq.actor(...)` at register time."""
        actor = LazyActor(_fn, crontab="*/5 * * * *", queue_name="cron")
        assert actor.crontab == "*/5 * * * *"
        assert actor.kw == {"queue_name": "cron"}

    def test_actor_is_none_before_register(self):
        actor = LazyActor(_fn)
        assert actor.actor is None

    def test_repr_includes_function_path(self):
        """The repr is what `register_*_jobs` logs — must surface the
        actor's importable name so a bad registration is debuggable."""
        actor = LazyActor(_fn)
        text = repr(actor)
        assert _fn.__module__ in text
        assert _fn.__name__ in text


class TestLazyActorCallSemantics:
    def test_calling_before_register_runs_function_directly(self):
        """The bare callable forwards to `fn(...)` — useful for
        local debugging and for in-process tests that don't need
        to spin up a broker."""
        actor = LazyActor(_fn)
        assert actor(41) == 42

    def test_call_preserves_args_and_kwargs(self):
        captured: list[tuple] = []

        def _spy(*args, **kwargs):
            captured.append((args, kwargs))
            return "ok"

        actor = LazyActor(_spy)
        assert actor(1, 2, key="value") == "ok"
        assert captured == [((1, 2), {"key": "value"})]


class TestLazyActorAttributeProxying:
    def test_getattr_raises_before_register(self):
        """Forwarding to `self.actor` only makes sense after register —
        before that, any unknown attribute should raise AttributeError
        instead of silently returning None."""
        actor = LazyActor(_fn)
        with pytest.raises(AttributeError):
            _ = actor.broker

    def test_send_assertion_before_register(self):
        """`.send()` is a thin shim over `self.actor.send()` and asserts
        the actor exists — calling it before register is a programming
        error that must fail loud, not silently no-op."""
        actor = LazyActor(_fn)
        with pytest.raises(AssertionError):
            actor.send()

    def test_send_with_options_assertion_before_register(self):
        actor = LazyActor(_fn)
        with pytest.raises(AssertionError):
            actor.send_with_options()


class TestLazyActorRegister:
    def test_register_creates_actor_on_broker(self):
        """Registering against a StubBroker is the smallest end-to-end
        path : `.actor` becomes a real dramatiq.Actor bound to the
        broker, and `.send()` enqueues a message instead of asserting."""
        broker = StubBroker()
        actor = LazyActor(_fn)

        actor.register(broker)

        assert actor.actor is not None
        # Bound to *our* broker, not the default global one.
        assert actor.actor.broker is broker

    def test_register_forwards_actor_kwargs(self):
        """`queue_name` and other dramatiq kwargs must reach the
        underlying `@actor(...)` call. We verify via the registered
        actor's resolved options."""
        broker = StubBroker()
        actor = LazyActor(_fn, queue_name="reports")

        actor.register(broker)

        assert actor.actor is not None
        assert actor.actor.queue_name == "reports"

    def test_send_after_register_enqueues_on_stub(self):
        """The StubBroker keeps messages in memory — exactly the
        contract that lets the test suite assert on enqueued work
        without spinning up Postgres + a worker process."""
        broker = StubBroker()
        actor = LazyActor(_fn)
        actor.register(broker)

        message = actor.send(123)

        assert message.actor_name == _fn.__name__
        assert message.args == (123,)


class TestLazyActorIsHashable:
    """`_actor_registry` in both `job.py` and `scheduler.py` is a
    `set[LazyActor]`. The class therefore needs to be hashable
    (object identity is fine — there's no custom __eq__/__hash__).
    Pin this so a future refactor doesn't accidentally break the
    decorator path."""

    def test_can_be_added_to_a_set(self):
        s: set[LazyActor] = set()
        s.add(LazyActor(_fn))
        s.add(LazyActor(_fn))
        # Two distinct instances, both kept ; identity-based hashing.
        assert len(s) == 2
