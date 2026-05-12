# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""End-to-end search indexing loop: signal → broker → actor → engine.

The other integration tests in this directory call the actor function
directly via ``reindex_from_source.fn(...)``, bypassing the Dramatiq
broker. These tests instead exercise the *real* ``.send()`` path:

1. A domain receiver enqueues a message into the StubBroker.
2. We pull the encoded message off the queue.
3. We decode it and dispatch to the registered actor.
4. We assert the side effect (engine state) is what we expect.

This catches anything that would break the actor registration, the
message encoding, or the source_type/id arg dispatch — none of which
the ``.fn()``-based tests touch.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import TYPE_CHECKING

import dramatiq
import pytest
import svcs.flask
from dramatiq.brokers.stub import StubBroker
from dramatiq.message import Message
from wesh.backends.filedb.filestore import RamStorage

from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.modules.search.engine import SearchEngine
from app.modules.search.receivers import _on_article_published
from app.modules.wire.models import ArticlePost
from app.signals import article_published

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def test_engine(app) -> Iterator[SearchEngine]:
    engine = SearchEngine(RamStorage())
    previous = svcs.flask.overwrite_value(SearchEngine, engine)
    try:
        yield engine
    finally:
        if previous is not None:
            svcs.flask.overwrite_value(SearchEngine, previous)


@pytest.fixture
def stub_broker() -> StubBroker:
    """The app's broker should already be a StubBroker under TESTING.
    We just flush it before each test so prior messages don't leak.
    """
    broker = dramatiq.get_broker()
    assert isinstance(broker, StubBroker), (
        "tests must run with the StubBroker; "
        "init_dramatiq() should pick it up via TESTING=True"
    )
    broker.flush_all()
    return broker


def _drain_one(broker: StubBroker, queue_name: str = "default") -> Message:
    """Pop one message off ``queue_name`` and decode it. Fails the
    test if the queue is empty."""
    queue = broker.queues[queue_name]
    raw = queue.get_nowait()
    queue.task_done()
    return Message.decode(raw)


def _dispatch(broker: StubBroker, message: Message) -> None:
    """Invoke the actor function for ``message`` synchronously. Skips
    the worker thread machinery to keep tests in the request's SQLA
    session — equivalent to what a real worker would do once the
    request transaction has committed.
    """
    actor = broker.get_actor(message.actor_name)
    actor.fn(*message.args, **message.kwargs)


class TestSignalToEngineLoop:
    def test_article_signal_enqueues_and_indexes(
        self, app, db_session, stub_broker, test_engine
    ):
        """The full chain: domain signal fires → search receiver
        enqueues → message is on the broker → dispatching it indexes
        the post in the engine.
        """
        with app.test_request_context():
            # Set up the wire-side mirror that the actor will look up.
            owner = User(email="loop_owner@example.com")
            db_session.add(owner)
            db_session.flush()
            post = ArticlePost(
                owner=owner,
                title="Full loop article",
                content="Body about distributed systems.",
                status=PublicationStatus.PUBLIC,
                published_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
            post.newsroom_id = 12345
            db_session.add(post)
            db_session.flush()

            # Fire the *search* receiver directly: firing the actual
            # blinker signal would also invoke wire/receivers.py which
            # expects a real wip Article model — that's not what we're
            # testing here.
            _on_article_published(SimpleNamespace(id=12345))

            # Message should now be on the broker.
            message = _drain_one(stub_broker)
            assert message.actor_name == "reindex_from_source"
            assert tuple(message.args) == ("article", 12345)
            assert message.kwargs == {}

            # Dispatch the message: this should reach the engine.
            _dispatch(stub_broker, message)

            hits = test_engine.search("distributed systems")
            assert len(hits) == 1
            assert hits[0]["title"] == "Full loop article"

    def test_search_receiver_is_connected_to_article_published(self):
        """The search receiver must be subscribed to the domain signal
        — otherwise publishing an article would never enqueue a job.

        We inspect blinker's receiver registry rather than firing the
        signal: firing it would also invoke ``wire/receivers.py`` and
        ``events/event_receiver.py``, which expect richer payloads,
        and disconnecting them temporarily is fragile (test ordering
        becomes load-bearing).
        """
        # blinker stores either a strong ref or a weakref to each
        # connected callable; resolving both forms gives us the
        # underlying function objects.
        connected = []
        for r in article_published.receivers.values():
            target = r() if callable(r) and not hasattr(r, "__func__") else r
            if target is not None:
                connected.append(target)

        names = {getattr(fn, "__name__", "") for fn in connected}
        assert "_on_article_published" in names, (
            f"search receiver not connected to article_published; "
            f"connected receivers: {names}"
        )
