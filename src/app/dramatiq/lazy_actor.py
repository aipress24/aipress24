"""Lazy actor implementation for delayed Dramatiq registration."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from types import FunctionType

import dramatiq


class LazyActor:
    """Intermediate object that registers actor on broker and call.

    Allows function decoration before broker is available.
    """

    fn: FunctionType
    crontab: str | None
    kw: dict
    actor: dramatiq.Actor | None = None

    def __init__(self, fn, **kw) -> None:
        """Initialize lazy actor with function and options.

        Args:
            fn: Function to wrap as an actor.
            **kw: Keyword arguments for actor configuration.
        """
        self.fn = fn
        self.crontab = kw.pop("crontab", None)
        self.kw = kw
        # self.actor = None

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.fn.__module__}.{self.fn.__name__}>"

    def __call__(self, *a, **kw):
        return self.fn(*a, **kw)

    def __getattr__(self, name):
        if not self.actor:
            raise AttributeError(name)
        return getattr(self.actor, name)

    def register(self, broker) -> None:
        """Register this lazy actor with a Dramatiq broker.

        Args:
            broker: Dramatiq broker to register with.
        """
        self.actor = dramatiq.actor(broker=broker, **self.kw)(self.fn)

    # Next is regular actor API.

    def send(self, *a, **kw):
        """Send message to actor queue.

        Args:
            *a: Positional arguments.
            **kw: Keyword arguments.

        Returns:
            Message instance.
        """
        assert self.actor
        return self.actor.send(*a, **kw)

    def send_with_options(self, *a, **kw):
        """Send message to actor queue with options.

        Args:
            *a: Positional arguments.
            **kw: Keyword arguments.

        Returns:
            Message instance.
        """
        assert self.actor
        return self.actor.send_with_options(*a, **kw)
