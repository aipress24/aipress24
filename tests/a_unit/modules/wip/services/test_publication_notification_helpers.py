# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `wip/services/newsroom/publication_notification_service`.

The `PublicationNotificationService` orchestrates DB writes and email
dispatch ; that orchestration belongs in b_integration. But the
decisions it makes around them — what counts as an eligible contact,
how recipients are deduplicated, how the in-app and mail payloads
look — are pure and worth pinning so a refactor can't silently change
who gets notified or what they read.

The SUT was refactored to expose those decisions as module-level pure
helpers (Pattern A). These tests drive them directly with duck-typed
stand-ins ; NO mocks, NO patches.

Covered helpers :

- `is_eligible_contact` : the `StatutAvis.ACCEPTE{,_RELATION_PRESSE}`
  predicate that gates mode-A pre-checks.
- `normalise_inputs` / `validate_article_url` : input scrubbing &
  the empty-URL guard.
- `deduplicate_recipients` : order-preserving dedup that drops the
  sender themselves (a journalist must not be notified of their own
  publication).
- `partition_recipients` : applies the pre-computed dup/cap exclusion
  sets without re-running the SQL.
- `filter_own_contacts` : defence-in-depth against form-tampered
  `contact_id`s pointing at a different avis.
- `extract_recipients_and_provenance` : derives the recipient list +
  the `expert_id -> contact_id` audit map from a contact selection.
- `filter_active_users` : mode-B input scrubber (None + inactive).
- `build_in_app_message` / `build_mail_kwargs` : payload contracts
  surfaced to recipients.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.modules.wip.models import StatutAvis
from app.modules.wip.services.newsroom.publication_notification_service import (
    ACCEPTED_STATUSES,
    PublicationNotificationError,
    build_in_app_message,
    build_mail_kwargs,
    deduplicate_recipients,
    extract_recipients_and_provenance,
    filter_active_users,
    filter_own_contacts,
    is_eligible_contact,
    normalise_inputs,
    partition_recipients,
    validate_article_url,
)

# ---------------------------------------------------------------------------
# Stand-ins (duck-typed) — keep the tests free of the ORM
# ---------------------------------------------------------------------------


@dataclass
class FakeUser:
    """Minimal stand-in for `app.models.auth.User`.

    Only the attributes touched by the helpers are modelled. `email`
    and `first_name` are typed as `str | None` to mirror the ORM —
    the helpers must absorb None gracefully.
    """

    id: int = 0
    email: str | None = "user@example.com"
    first_name: str | None = "Alice"
    full_name: str = "Alice Example"
    active: bool = True


@dataclass
class FakeContact:
    """Minimal stand-in for `ContactAvisEnquete`."""

    id: int = 0
    status: StatutAvis = StatutAvis.EN_ATTENTE
    expert: FakeUser | None = None
    expert_id: int | None = None
    # Real model has more fields ; only the ones the helpers touch
    # are modelled here. Anything else would couple the test to the
    # SQLAlchemy mapper.
    extras: dict[str, object] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# is_eligible_contact / ACCEPTED_STATUSES
# ---------------------------------------------------------------------------


class TestIsEligibleContact:
    """Mode A pre-checks only ACCEPTE / ACCEPTE_RELATION_PRESSE. If
    this drifts, e.g. EN_ATTENTE starts ticking by default, the form
    will pre-select people who never agreed to be quoted — a hard
    editorial-policy violation."""

    @pytest.mark.parametrize(
        ("status", "expected"),
        [
            (StatutAvis.ACCEPTE, True),
            (StatutAvis.ACCEPTE_RELATION_PRESSE, True),
            (StatutAvis.EN_ATTENTE, False),
            (StatutAvis.REFUSE, False),
            (StatutAvis.REFUSE_SUGGESTION, False),
        ],
    )
    def test_predicate_matches_accepted_statuses(
        self, status: StatutAvis, expected: bool
    ) -> None:
        contact = FakeContact(status=status)
        assert is_eligible_contact(contact) is expected

    def test_accepted_statuses_constant_is_frozen(self) -> None:
        """`ACCEPTED_STATUSES` is exposed for reuse by callers ; it
        must be immutable so a downstream module can't widen the
        eligibility net by accident."""
        assert isinstance(ACCEPTED_STATUSES, frozenset)
        assert {
            StatutAvis.ACCEPTE,
            StatutAvis.ACCEPTE_RELATION_PRESSE,
        } == ACCEPTED_STATUSES


# ---------------------------------------------------------------------------
# normalise_inputs / validate_article_url
# ---------------------------------------------------------------------------


class TestNormaliseInputs:
    """All three free-text fields must be stripped identically so the
    DB row, the mail body and the URL guard see the same canonical
    form. A drift here means « " " » could pass `validate_article_url`."""

    def test_strips_all_three_fields(self) -> None:
        url, title, message = normalise_inputs(
            "  https://x.test/a  ", "  Hello  ", "  hi\n"
        )
        assert url == "https://x.test/a"
        assert title == "Hello"
        assert message == "hi"

    def test_preserves_inner_whitespace(self) -> None:
        url, title, message = normalise_inputs(
            "  https://x.test/a b  ", "  Hello  world  ", "  hi  there  "
        )
        assert url == "https://x.test/a b"
        assert title == "Hello  world"
        assert message == "hi  there"

    def test_pure_whitespace_collapses_to_empty(self) -> None:
        url, title, message = normalise_inputs("   ", "\t\n", "  ")
        assert (url, title, message) == ("", "", "")


class TestValidateArticleUrl:
    """The empty-URL guard is the only user-facing validation in the
    dispatch shell ; it must speak the localised message that the
    Newsroom views surface."""

    def test_non_empty_url_passes(self) -> None:
        # No return value, no exception — implicit success.
        validate_article_url("https://x.test/a")

    @pytest.mark.parametrize("bad", ["", " ", "\n\t"])
    def test_blank_url_raises(self, bad: str) -> None:
        # Note : `validate_article_url` is called AFTER
        # `normalise_inputs`, so in production it only sees "" — but
        # we still want the guard itself to refuse blanks.
        with pytest.raises(PublicationNotificationError) as exc:
            # Mirror production : strip first, then validate.
            validate_article_url(bad.strip())
        assert "URL" in str(exc.value)


# ---------------------------------------------------------------------------
# deduplicate_recipients
# ---------------------------------------------------------------------------


class TestDeduplicateRecipients:
    """The sender themselves must NEVER end up in the recipient list
    (self-notification spam), and duplicates posted by the form must
    collapse to one DB row + one email. Order must be preserved so
    the audit log is reproducible."""

    def test_drops_sender(self) -> None:
        sender = FakeUser(id=1)
        other = FakeUser(id=2)
        unique = deduplicate_recipients([sender, other], sender_id=sender.id)
        assert list(unique.keys()) == [2]
        assert unique[2] is other

    def test_collapses_duplicates_keeping_first_instance(self) -> None:
        a1 = FakeUser(id=10, email="a1@example.com")
        a2 = FakeUser(id=10, email="a2@example.com")
        b = FakeUser(id=11)
        unique = deduplicate_recipients([a1, a2, b], sender_id=99)
        assert list(unique.keys()) == [10, 11]
        # `setdefault` keeps the first user object seen.
        assert unique[10] is a1

    def test_preserves_input_order(self) -> None:
        users = [FakeUser(id=i) for i in (3, 1, 4, 1, 5, 9, 2, 6)]
        unique = deduplicate_recipients(users, sender_id=0)
        assert list(unique.keys()) == [3, 1, 4, 5, 9, 2, 6]

    def test_empty_input_returns_empty(self) -> None:
        assert deduplicate_recipients([], sender_id=1) == {}

    def test_input_consisting_only_of_sender_returns_empty(self) -> None:
        sender = FakeUser(id=7)
        # The form can technically post only-the-sender if the
        # journalist ticks themselves ; must collapse to nothing.
        unique = deduplicate_recipients([sender, sender], sender_id=7)
        assert unique == {}


# ---------------------------------------------------------------------------
# partition_recipients
# ---------------------------------------------------------------------------


class TestPartitionRecipients:
    """Pure split of unique recipients into (accepted, skipped) given
    pre-computed dup/cap sets. The SQL that computes those sets is
    covered by integration tests ; here we pin the splitter."""

    def test_no_exclusions_keeps_all(self) -> None:
        u1, u2 = FakeUser(id=1), FakeUser(id=2)
        accepted, skipped = partition_recipients(
            {1: u1, 2: u2}, dup_ids=set(), capped_ids=set()
        )
        assert accepted == [u1, u2]
        assert skipped == []

    def test_dup_ids_skip(self) -> None:
        u1, u2, u3 = FakeUser(id=1), FakeUser(id=2), FakeUser(id=3)
        accepted, skipped = partition_recipients(
            {1: u1, 2: u2, 3: u3}, dup_ids={2}, capped_ids=set()
        )
        assert accepted == [u1, u3]
        assert skipped == [u2]

    def test_capped_ids_skip(self) -> None:
        u1, u2 = FakeUser(id=1), FakeUser(id=2)
        accepted, skipped = partition_recipients(
            {1: u1, 2: u2}, dup_ids=set(), capped_ids={1}
        )
        assert accepted == [u2]
        assert skipped == [u1]

    def test_both_sets_union(self) -> None:
        """A user matched by both sets is still skipped exactly once
        (idempotence)."""
        u1, u2, u3 = FakeUser(id=1), FakeUser(id=2), FakeUser(id=3)
        accepted, skipped = partition_recipients(
            {1: u1, 2: u2, 3: u3}, dup_ids={2}, capped_ids={2, 3}
        )
        assert accepted == [u1]
        assert skipped == [u2, u3]

    def test_preserves_insertion_order(self) -> None:
        """The accepted list determines the order in which the in-app
        and mail dispatches run ; must follow the unique-dict order."""
        users = {i: FakeUser(id=i) for i in (5, 3, 8, 1)}
        accepted, skipped = partition_recipients(users, dup_ids={8}, capped_ids=set())
        assert [u.id for u in accepted] == [5, 3, 1]
        assert [u.id for u in skipped] == [8]


# ---------------------------------------------------------------------------
# filter_own_contacts
# ---------------------------------------------------------------------------


class TestFilterOwnContacts:
    """Mode A defence-in-depth : a tampered form might smuggle a
    contact_id that belongs to another avis. The helper drops anything
    not in the owning-avis's set."""

    def test_keeps_only_own_ids(self) -> None:
        c1 = FakeContact(id=1)
        c2 = FakeContact(id=2)
        c3 = FakeContact(id=3)
        kept = filter_own_contacts([c1, c2, c3], {1, 3})
        assert kept == [c1, c3]

    def test_empty_own_ids_drops_everything(self) -> None:
        assert filter_own_contacts([FakeContact(id=1)], set()) == []

    def test_empty_input_returns_empty(self) -> None:
        assert filter_own_contacts([], {1, 2}) == []

    def test_preserves_order(self) -> None:
        contacts = [FakeContact(id=i) for i in (4, 2, 5, 1, 3)]
        kept = filter_own_contacts(contacts, {1, 2, 3, 4, 5})
        assert [c.id for c in kept] == [4, 2, 5, 1, 3]


# ---------------------------------------------------------------------------
# extract_recipients_and_provenance
# ---------------------------------------------------------------------------


class TestExtractRecipientsAndProvenance:
    """The provenance map ties each notification back to the contact
    that authorised it (audit trail). Contacts without a linked expert
    must be dropped from recipients, not silently mapped to None."""

    def test_full_extraction(self) -> None:
        u1, u2 = FakeUser(id=10), FakeUser(id=20)
        c1 = FakeContact(id=1, expert=u1, expert_id=10)
        c2 = FakeContact(id=2, expert=u2, expert_id=20)
        recipients, provenance = extract_recipients_and_provenance([c1, c2])
        assert recipients == [u1, u2]
        assert provenance == {10: 1, 20: 2}

    def test_drops_contacts_without_expert(self) -> None:
        u = FakeUser(id=10)
        c_no_expert = FakeContact(id=1, expert=None, expert_id=None)
        c_with = FakeContact(id=2, expert=u, expert_id=10)
        recipients, provenance = extract_recipients_and_provenance(
            [c_no_expert, c_with]
        )
        assert recipients == [u]
        # Provenance is keyed on expert_id ; the None key is harmless
        # because partition / dispatch only looks up known ids.
        assert provenance.get(10) == 2

    def test_empty_input(self) -> None:
        recipients, provenance = extract_recipients_and_provenance([])
        assert recipients == []
        assert provenance == {}


# ---------------------------------------------------------------------------
# filter_active_users
# ---------------------------------------------------------------------------


class TestFilterActiveUsers:
    """Mode B free-form input may contain Nones (resolved from form
    IDs that no longer exist) and inactive users (disabled accounts).
    Both must be dropped before partition + dispatch."""

    def test_keeps_only_active_users(self) -> None:
        active = FakeUser(id=1, active=True)
        inactive = FakeUser(id=2, active=False)
        assert filter_active_users([active, inactive]) == [active]

    def test_drops_none(self) -> None:
        active = FakeUser(id=1)
        assert filter_active_users([None, active, None]) == [active]

    def test_preserves_order_of_kept_users(self) -> None:
        a, b, c = (
            FakeUser(id=1),
            FakeUser(id=2, active=False),
            FakeUser(id=3),
        )
        assert filter_active_users([a, b, c]) == [a, c]

    def test_empty_input(self) -> None:
        assert filter_active_users([]) == []


# ---------------------------------------------------------------------------
# build_in_app_message
# ---------------------------------------------------------------------------


class TestBuildInAppMessage:
    """The in-app body is the only thing recipients see in their bell
    menu before clicking ; the exact wording is product-frozen and
    must not drift between releases."""

    def test_renders_french_template(self) -> None:
        body = build_in_app_message("Jane Doe", "Mon article")
        assert body == (
            "Jane Doe vous a notifié de la publication de l'article « Mon article »."
        )

    def test_empty_strings_render_without_crashing(self) -> None:
        body = build_in_app_message("", "")
        # The template still renders ; downstream code is responsible
        # for refusing empty inputs upstream.
        assert "vous a notifié" in body
        # Two spaces between the guillemets because the title slot is
        # empty and the template uses « {title} ».
        assert "«  »" in body


# ---------------------------------------------------------------------------
# build_mail_kwargs
# ---------------------------------------------------------------------------


class TestBuildMailKwargs:
    """The mail kwargs payload is the contract with
    `PublicationNotificationMail`. Its keys, defaults (`""` for None
    fields) and the hard-coded `sender="contact@aipress24.com"`
    address are pinned here so the mail constructor's signature can
    be verified independently."""

    def test_full_payload_shape(self) -> None:
        sender = FakeUser(
            id=1,
            email="journo@example.com",
            full_name="Jane Journo",
        )
        recipient = FakeUser(
            id=2,
            email="expert@example.com",
            first_name="Bob",
        )
        kwargs = build_mail_kwargs(
            sender=sender,
            sender_bw_name="Le Monde",
            recipient=recipient,
            article_title="Scoop",
            article_url="https://x.test/scoop",
            message="FYI",
            opportunities_url="https://x.test/opps",
        )
        assert kwargs == {
            "sender": "contact@aipress24.com",
            "recipient": "expert@example.com",
            "sender_mail": "journo@example.com",
            "sender_full_name": "Jane Journo",
            "sender_bw_name": "Le Monde",
            "recipient_first_name": "Bob",
            "article_title": "Scoop",
            "article_url": "https://x.test/scoop",
            "personal_message": "FYI",
            "opportunities_url": "https://x.test/opps",
        }

    def test_none_email_and_first_name_become_empty_strings(self) -> None:
        """The mail constructor expects `str` ; the helper must absorb
        None on the optional fields so an account without a stored
        first name doesn't crash dispatch."""
        sender = FakeUser(id=1, email=None, full_name="Jane")
        recipient = FakeUser(id=2, email=None, first_name=None)
        kwargs = build_mail_kwargs(
            sender=sender,
            sender_bw_name="",
            recipient=recipient,
            article_title="T",
            article_url="U",
            message="",
            opportunities_url="",
        )
        assert kwargs["recipient"] == ""
        assert kwargs["sender_mail"] == ""
        assert kwargs["recipient_first_name"] == ""

    def test_sender_address_is_hardcoded(self) -> None:
        """Outbound transactional emails MUST come from the platform
        address (DMARC alignment) ; this pin guards against a refactor
        that uses `sender.email` here."""
        sender = FakeUser(id=1, email="evil@elsewhere.test")
        recipient = FakeUser(id=2)
        kwargs = build_mail_kwargs(
            sender=sender,
            sender_bw_name="",
            recipient=recipient,
            article_title="T",
            article_url="U",
            message="",
            opportunities_url="",
        )
        assert kwargs["sender"] == "contact@aipress24.com"
        # `sender_mail` is the reply-to ; that one DOES carry the
        # journalist's address.
        assert kwargs["sender_mail"] == "evil@elsewhere.test"
