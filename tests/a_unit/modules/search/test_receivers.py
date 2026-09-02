# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Verify that the receivers translate signal payloads to the right
``reindex_from_source.send(source_type, source_id)`` call, and that every
signal is wired to one.

We call the receiver functions directly rather than firing the signals
through blinker, because firing the real signals would also invoke the
unrelated wire/event mirroring receivers, which expect richer payloads.
Job *behaviour* is exercised in
``tests/b_integration/modules/search/test_jobs_and_rebuild.py``.

There used to be one test per signal — fifteen of them, calling fifteen
receivers whose bodies were identical in groups. The receivers are now
one per source type, so the payload tests are one per source type too,
and what the extra tests used to imply — that each signal reaches a
receiver — is asserted directly below.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.modules.search import receivers
from app.signals import (
    article_published,
    article_unpublished,
    article_updated,
    communique_published,
    communique_unpublished,
    communique_updated,
    event_published,
    event_unpublished,
    event_updated,
    marketplace_published,
    marketplace_unpublished,
    org_activated,
    org_deactivated,
    user_activated,
    user_deactivated,
)


@pytest.fixture
def captured_sends(monkeypatch) -> list[tuple]:
    calls: list[tuple] = []

    def _capture(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr(receivers.reindex_from_source, "send", _capture)
    return calls


def _payload(pk: int) -> SimpleNamespace:
    return SimpleNamespace(id=pk)


@pytest.mark.parametrize(
    ("receiver", "source_type"),
    [
        (receivers._reindex_article, "article"),
        (receivers._reindex_press_release, "press_release"),
        (receivers._reindex_event, "event"),
        (receivers._reindex_marketplace, "marketplace"),
        (receivers._reindex_user, "user"),
        (receivers._reindex_organisation, "organisation"),
    ],
)
def test_receiver_enqueues_its_source_type(captured_sends, receiver, source_type):
    receiver(_payload(42))

    assert captured_sends == [((source_type, 42), {})]


@pytest.mark.parametrize(
    ("signal", "receiver"),
    [
        (article_published, receivers._reindex_article),
        (article_unpublished, receivers._reindex_article),
        (article_updated, receivers._reindex_article),
        (communique_published, receivers._reindex_press_release),
        (communique_unpublished, receivers._reindex_press_release),
        (communique_updated, receivers._reindex_press_release),
        (event_published, receivers._reindex_event),
        (event_unpublished, receivers._reindex_event),
        (event_updated, receivers._reindex_event),
        (marketplace_published, receivers._reindex_marketplace),
        (marketplace_unpublished, receivers._reindex_marketplace),
        (user_activated, receivers._reindex_user),
        (user_deactivated, receivers._reindex_user),
        (org_activated, receivers._reindex_organisation),
        (org_deactivated, receivers._reindex_organisation),
    ],
)
def test_every_signal_reaches_its_receiver(signal, receiver):
    """Stacked `connect` decorators are easy to drop one of by accident.

    Inspecting `signal.receivers` fires nothing, so this stays safe for
    the reason the module docstring gives.
    """
    connected = [
        target
        for ref in signal.receivers.values()
        if (target := ref() if callable(ref) and not hasattr(ref, "__func__") else ref)
        is not None
    ]

    assert receiver in connected, (
        f"{receiver.__name__} not connected to the signal; "
        f"connected: {[getattr(fn, '__name__', fn) for fn in connected]}"
    )
