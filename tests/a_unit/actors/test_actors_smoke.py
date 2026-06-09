# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Smoke tests for the 3 production Dramatiq actors.

Each actor wraps a single service call via the `@job()` / `@crontab(...)`
decorators in `app.dramatiq.{job,scheduler}`. The wrapper itself is
covered by `tests/a_unit/dramatiq/test_lazy_actor.py`; here we pin :

- the actor object is a `LazyActor` (i.e. the decorator survived
  module import without raising),
- invoking the actor directly (pre-broker) runs the delegate service
  function with the right arguments,
- cron actors carry their schedule.

That's all that's worth asserting at this level — the delegate
services (`generate_justificatif_pdf`, `update_reputations`,
`rebuild_index`) have their own test suites.
"""

from __future__ import annotations

from unittest.mock import patch

from app.actors.justificatif import generate_justificatif
from app.actors.reputation import update_reputations
from app.actors.search import rebuild_search_index
from app.dramatiq.lazy_actor import LazyActor
from app.services.emails import EmailService


class TestJustificatifActor:
    def test_is_a_lazy_actor(self):
        assert isinstance(generate_justificatif, LazyActor)

    def test_runs_the_delegate_with_purchase_id(self):
        """Direct invocation (the pre-broker path used in tests +
        local debugging) must forward to
        `wire.services.justificatif.generate_justificatif_pdf`.

        The actor does `from … import generate_justificatif_pdf` lazily
        inside the function body, so the patch site is the source
        module — patching the actor module wouldn't catch the lookup."""
        with patch(
            "app.modules.wire.services.justificatif.generate_justificatif_pdf"
        ) as mock_pdf:
            generate_justificatif(42)
        mock_pdf.assert_called_once_with(42)


class TestReputationActor:
    def test_is_a_lazy_actor_with_hourly_schedule(self):
        assert isinstance(update_reputations, LazyActor)
        # HH:00 — runs every hour, deliberately offset from
        # `rebuild_search_index` (HH:15) so they don't pile up.
        assert update_reputations.crontab == "0 * * * *"

    def test_invokes_reputation_service(self, app):
        """The cron job recomputes reputations and emails the result.
        We patch the underlying service + the EmailService class so
        the test stays purely in-process — no real DB / SMTP touch.

        Use a real Flask app context so svcs's container has somewhere
        to resolve `EmailService`, and patch the email service's
        send method directly so we don't depend on container internals."""
        with (
            app.app_context(),
            patch(
                "app.actors.reputation.reputation.update_reputations"
            ) as mock_update,
            patch.object(EmailService, "send_system_email") as mock_send,
        ):
            update_reputations()

        mock_update.assert_called_once_with(add_noise=True)
        mock_send.assert_called_once_with("Reputations updated")


class TestSearchRebuildActor:
    def test_is_a_lazy_actor_with_offset_schedule(self):
        assert isinstance(rebuild_search_index, LazyActor)
        # Runs at HH:15 to avoid colliding with the reputation actor
        # (HH:00). Cron expression checked verbatim so a future
        # refactor that drops the offset gets caught.
        assert rebuild_search_index.crontab == "15 * * * *"

    def test_invokes_search_cli_rebuild(self):
        # `rebuild_index` is imported at the top of
        # `app.actors.search`, so the patch site is the actor module.
        with patch("app.actors.search.rebuild_index") as mock_rebuild:
            mock_rebuild.return_value = {"article": 5, "user": 10}
            rebuild_search_index()
        mock_rebuild.assert_called_once_with(show_progress=False)
