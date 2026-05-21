# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Verify that the receivers translate signal payloads to the right
``reindex_from_source.send(source_type, source_id)`` call.

We call the receiver functions directly rather than firing the signals
through blinker, because firing the real signals would also invoke the
unrelated wire/event mirroring receivers, which expect richer payloads.
Job *behaviour* is exercised in
``tests/b_integration/modules/search/test_jobs_and_rebuild.py``.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.modules.search import receivers


@pytest.fixture
def captured_sends(monkeypatch) -> list[tuple]:
    calls: list[tuple] = []

    def _capture(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr(receivers.reindex_from_source, "send", _capture)
    return calls


def _payload(pk: int) -> SimpleNamespace:
    return SimpleNamespace(id=pk)


def test_article_published_enqueues_with_article_type(captured_sends):
    receivers._on_article_published(_payload(42))
    assert captured_sends == [(("article", 42), {})]


def test_article_unpublished_enqueues(captured_sends):
    receivers._on_article_unpublished(_payload(43))
    assert captured_sends == [(("article", 43), {})]


def test_article_updated_enqueues(captured_sends):
    receivers._on_article_updated(_payload(44))
    assert captured_sends == [(("article", 44), {})]


def test_communique_published_uses_press_release_type(captured_sends):
    receivers._on_communique_published(_payload(100))
    assert captured_sends == [(("press_release", 100), {})]


def test_communique_unpublished_enqueues(captured_sends):
    receivers._on_communique_unpublished(_payload(101))
    assert captured_sends == [(("press_release", 101), {})]


def test_communique_updated_enqueues(captured_sends):
    receivers._on_communique_updated(_payload(102))
    assert captured_sends == [(("press_release", 102), {})]


def test_event_published_enqueues_with_event_type(captured_sends):
    receivers._on_event_published(_payload(200))
    assert captured_sends == [(("event", 200), {})]


def test_event_unpublished_enqueues(captured_sends):
    receivers._on_event_unpublished(_payload(201))
    assert captured_sends == [(("event", 201), {})]


def test_event_updated_enqueues(captured_sends):
    receivers._on_event_updated(_payload(202))
    assert captured_sends == [(("event", 202), {})]


def test_marketplace_published_uses_marketplace_source_type(captured_sends):
    receivers._on_marketplace_published(_payload(300))
    assert captured_sends == [(("marketplace", 300), {})]


def test_marketplace_unpublished_enqueues(captured_sends):
    receivers._on_marketplace_unpublished(_payload(301))
    assert captured_sends == [(("marketplace", 301), {})]


# Group receiver tests retirés le 2026-05-21 — les Groupes ne sont
# plus enregistrés dans le moteur de recherche.


def test_user_activated_enqueues(captured_sends):
    receivers._on_user_activated(_payload(500))
    assert captured_sends == [(("user", 500), {})]


def test_user_deactivated_enqueues(captured_sends):
    receivers._on_user_deactivated(_payload(501))
    assert captured_sends == [(("user", 501), {})]


def test_org_activated_enqueues(captured_sends):
    receivers._on_org_activated(_payload(600))
    assert captured_sends == [(("organisation", 600), {})]


def test_org_deactivated_enqueues(captured_sends):
    receivers._on_org_deactivated(_payload(601))
    assert captured_sends == [(("organisation", 601), {})]
