# Copyright (c) 2021-2026, Abilian SAS & TCA
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the pure rules in `wip/services/newsroom/sujet_accept`.

`accept_sujet_as_commande` is the orchestrator — it pulls together the
basic precondition check, a DB-coupled rédac-chef check, and a
Commande field-mapping step before flushing. The DB-coupled bits are
exercised at b_integration (`test_sujet.py::TestSujetAcceptAction`).

This file pins the three pure pieces :

* `validate_basic_acceptance` — org-match + sujet-status preconditions
* `build_commande_payload` — the field mapping the new Commande gets
* `is_notification_eligible` — the skip rule for the author cloche

Microsecond-speed, no DB. Pin every business rule so a refactor (or a
quick « let's tweak this default ») surfaces in CI within a second.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.models.lifecycle import PublicationStatus
from app.modules.wip.services.newsroom.sujet_accept import (
    build_commande_payload,
    is_notification_eligible,
    validate_basic_acceptance,
)

# ---------------------------------------------------------------------------
# validate_basic_acceptance
# ---------------------------------------------------------------------------


class TestValidateBasicAcceptance:
    def test_org_match_and_public_status_passes_silently(self):
        # No exception — basic preconditions are met. The rédac-chef
        # check happens in the orchestrator.
        validate_basic_acceptance(
            accepter_org_id=42,
            sujet_media_id=42,
            sujet_status=PublicationStatus.PUBLIC,
        )

    def test_org_mismatch_raises_authorization_error(self):
        with pytest.raises(ValueError, match="not authorized"):
            validate_basic_acceptance(
                accepter_org_id=42,
                sujet_media_id=99,
                sujet_status=PublicationStatus.PUBLIC,
            )

    def test_none_accepter_org_id_is_a_mismatch(self):
        """A user without `organisation_id` should not be able to
        accept anyone's sujet. Pin the None vs int distinction so a
        future refactor that swaps `None == None` for a truthy-check
        doesn't silently let orphan users through."""
        with pytest.raises(ValueError, match="not authorized"):
            validate_basic_acceptance(
                accepter_org_id=None,
                sujet_media_id=42,
                sujet_status=PublicationStatus.PUBLIC,
            )

    def test_draft_sujet_cannot_be_accepted(self):
        """A DRAFT sujet hasn't been offered — accepting it would
        skip the publication step."""
        with pytest.raises(ValueError, match="not in PUBLIC status"):
            validate_basic_acceptance(
                accepter_org_id=42,
                sujet_media_id=42,
                sujet_status=PublicationStatus.DRAFT,
            )

    def test_archived_sujet_cannot_be_accepted_again(self):
        """An ARCHIVED sujet has already been accepted (or refused) —
        a second `accept()` would silently duplicate the Commande
        and confuse the author with two cloches. Pin so the
        idempotency-by-state guarantee can't regress."""
        with pytest.raises(ValueError, match="not in PUBLIC status"):
            validate_basic_acceptance(
                accepter_org_id=42,
                sujet_media_id=42,
                sujet_status=PublicationStatus.ARCHIVED,
            )

    def test_org_mismatch_short_circuits_status_check(self):
        """When BOTH preconditions fail, the org-mismatch error wins —
        we want operators to fix the auth shape first (it's a security
        signal), not the status shape (which is a workflow signal)."""
        with pytest.raises(ValueError, match="not authorized"):
            validate_basic_acceptance(
                accepter_org_id=42,
                sujet_media_id=99,
                sujet_status=PublicationStatus.DRAFT,
            )


# ---------------------------------------------------------------------------
# build_commande_payload
# ---------------------------------------------------------------------------


def _sujet_stub(
    *,
    media_id: int = 42,
    titre: str = "Sujet titre",
    contenu: str = "Sujet contenu",
    brief: str | None = "le brief",
    date_limite_validite: datetime | None = None,
    date_parution_prevue: datetime | None = None,
):
    """Duck-typed sujet — `build_commande_payload` reads only the
    listed attributes, so a `SimpleNamespace` matches the contract
    without dragging in the Sujet ORM row (and its dependencies)."""
    return SimpleNamespace(
        media_id=media_id,
        titre=titre,
        contenu=contenu,
        brief=brief,
        date_limite_validite=date_limite_validite or datetime(2026, 12, 31, tzinfo=UTC),
        date_parution_prevue=date_parution_prevue or datetime(2026, 6, 30, tzinfo=UTC),
    )


class TestBuildCommandePayload:
    def test_copies_content_fields_verbatim(self):
        sujet = _sujet_stub(titre="Mon titre", contenu="<p>Mon contenu</p>")
        payload = build_commande_payload(sujet, accepter_id=7)

        assert payload["titre"] == "Mon titre"
        assert payload["contenu"] == "<p>Mon contenu</p>"

    def test_owner_and_commanditaire_both_set_to_accepter(self):
        """The accepter (rédac chef) is BOTH the Commande's owner
        (controls edits) AND the commanditaire (the customer behind
        it). Pin so a future refactor that distinguishes the two
        doesn't silently route the « who pays » column to the wrong
        user."""
        payload = build_commande_payload(_sujet_stub(), accepter_id=7)

        assert payload["owner_id"] == 7
        assert payload["commanditaire_id"] == 7

    def test_media_id_mirrors_sujet(self):
        """The new commande lives in the rédac chef's own newsroom,
        not somewhere else."""
        sujet = _sujet_stub(media_id=99)
        payload = build_commande_payload(sujet, accepter_id=7)
        assert payload["media_id"] == 99

    def test_empty_brief_falls_back_to_empty_string(self):
        """Commande.brief is NOT NULL ; the author may have published
        without a brief, in which case we default to "" rather than
        propagate None and break the flush."""
        sujet = _sujet_stub(brief=None)
        payload = build_commande_payload(sujet, accepter_id=7)
        assert payload["brief"] == ""

    def test_brief_is_copied_when_present(self):
        sujet = _sujet_stub(brief="Specific brief text")
        payload = build_commande_payload(sujet, accepter_id=7)
        assert payload["brief"] == "Specific brief text"

    def test_status_defaults_to_draft(self):
        """The rédac chef adjusts before publishing — we don't auto-
        publish the materialised commande, that would skip review."""
        payload = build_commande_payload(_sujet_stub(), accepter_id=7)
        assert payload["status"] == PublicationStatus.DRAFT

    def test_dates_mirror_sujet(self):
        deadline = datetime(2026, 1, 31, tzinfo=UTC)
        publish = datetime(2026, 2, 15, tzinfo=UTC)
        sujet = _sujet_stub(date_limite_validite=deadline, date_parution_prevue=publish)
        payload = build_commande_payload(sujet, accepter_id=7)
        assert payload["date_limite_validite"] == deadline
        assert payload["date_parution_prevue"] == publish

    def test_bouclage_and_paiement_default_to_publication_date(self):
        """Commande requires `date_bouclage` AND `date_paiement` (NOT
        NULL). We default both to the publication date as a
        reasonable starting point — the rédac chef tweaks before
        publishing the commande. Pin so a refactor doesn't silently
        let nulls reach the flush."""
        publish = datetime(2026, 2, 15, tzinfo=UTC)
        sujet = _sujet_stub(date_parution_prevue=publish)
        payload = build_commande_payload(sujet, accepter_id=7)
        assert payload["date_bouclage"] == publish
        assert payload["date_paiement"] == publish


# ---------------------------------------------------------------------------
# is_notification_eligible
# ---------------------------------------------------------------------------


class TestIsNotificationEligible:
    def test_returns_true_for_real_user(self):
        author = SimpleNamespace(is_anonymous=False, full_name="A. Author")
        assert is_notification_eligible(author) is True

    def test_returns_false_for_none_author(self):
        """Sujet without resolved author (legacy data, deleted user) —
        skip cleanly rather than crash the orchestrator with an
        AttributeError on `None.full_name`."""
        assert is_notification_eligible(None) is False

    def test_returns_false_for_anonymous_user(self):
        """Flask-Login's AnonymousUserMixin carries `is_anonymous=True`.
        Posting an in-app cloche to anonymous is meaningless."""
        anon = SimpleNamespace(is_anonymous=True)
        assert is_notification_eligible(anon) is False

    def test_user_without_is_anonymous_attr_is_eligible(self):
        """A duck-typed user (stub, test fixture) that doesn't set
        `is_anonymous` defaults to NOT anonymous via getattr — the
        in-app notification fires."""
        plain = SimpleNamespace(full_name="Stub")
        assert is_notification_eligible(plain) is True
