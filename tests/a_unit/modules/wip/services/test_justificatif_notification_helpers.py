# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the pure helpers extracted from
`app.modules.wip.services.newsroom.justificatif_notification`.

Ticket #0195 wires a journalist's « Justificatif » action to selected
participants of one of their `AvisEnquete`. The orchestration entry
point (`notify_avis_participants_of_justificatif`) is a DB + mail
batch — its end-to-end behaviour is covered by b_integration. The
pieces tested here are the pure decision helpers that were factored
out so the policy can be pinned without spinning up a DB session,
a mail bus, or a Flask app context :

- `filter_allowed_recipients` — the anti-spam gate that drops any
  recipient id the form POST smuggled in. Without it a journalist
  could blast arbitrary users and inflate the rémunération counter.
- `resolve_media_name` — the (bw_name → name → em-dash) precedence
  table that decides what brand string the participant sees in the
  email subject / body. A silent regression would email participants
  with a blank media name.
- `build_in_app_message` — the French product copy embedding the
  journalist name and the article title in French guillemets.
- `build_mail_kwargs` — the call-site → `JustificatifInvitationMail`
  field routing. The mapping IS the contract. A swap (e.g.
  `enquete_title` ↔ `article_title`) would silently corrupt every
  participant email.
- `next_notification_count` — the `None → 0` defaulting + addition for
  `justificatif_notifications_count`. Downstream rémunération is
  computed off this counter.

No mocks. No patches. No fixture-based patching tricks — per the
project rule « Don't use mocks. Prefer stubs. Verify state, not
interaction. »
The helpers are pure : tests construct duck-typed stand-ins, call the
helper, and assert on the returned value.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.modules.wip.services.newsroom.justificatif_notification import (
    DEFAULT_SENDER_EMAIL,
    EM_DASH_FALLBACK,
    build_in_app_message,
    build_mail_kwargs,
    filter_allowed_recipients,
    next_notification_count,
    resolve_media_name,
)

# ----------------------------------------------------------------------
# Duck-typed stand-ins. We deliberately avoid the ORM — instantiating a
# real `User` / `ArticlePost` / `AvisEnquete` requires a Flask + DB
# context, and the autouse `db_session` fixture aborts the suite if
# anything leaks rows. Plain classes carry only the fields the helpers
# under test read.
# ----------------------------------------------------------------------


class _OrgLike:
    """Stand-in for `Organisation`. Selectively omit `bw_name` /
    `name` to exercise the `getattr(..., default)` branches inside
    `resolve_media_name`."""

    def __init__(self, *, bw_name: str = "", name: str = "") -> None:
        self.bw_name = bw_name
        self.name = name


class _UserLike:
    """Stand-in for `User`. The helpers read `email` and
    `full_name`."""

    def __init__(
        self,
        *,
        full_name: str = "Jane Reporter",
        email: str = "jane@example.com",
    ) -> None:
        self.full_name = full_name
        self.email = email


class _ArticleLike:
    """Stand-in for `ArticlePost`. The helpers read `title`."""

    def __init__(self, *, title: str = "Une enquête") -> None:
        self.title = title


class _AvisLike:
    """Stand-in for `AvisEnquete`. `build_mail_kwargs` reads only
    `titre` via `getattr(..., "titre", "")`."""

    def __init__(self, *, titre: str = "Enquête XYZ") -> None:
        self.titre = titre


# ----------------------------------------------------------------------
# filter_allowed_recipients
# ----------------------------------------------------------------------


class TestFilterAllowedRecipients:
    """`filter_allowed_recipients` is the anti-spam gate : it drops
    every recipient id that's not a legitimate `ContactAvisEnquete`
    participant of the avis.

    The function is pure : caller supplies the already-computed
    `allowed_ids` set (materialised from a SQL query in the
    imperative shell). Order of the input list must be preserved
    because downstream the orchestrator iterates and counts per id.
    """

    def test_keeps_only_ids_in_the_allowed_set(self) -> None:
        result = filter_allowed_recipients([1, 2, 3, 4], {2, 4})
        assert result == [2, 4]

    def test_drops_every_id_when_intersection_empty(self) -> None:
        """Forged form POST : the journalist submitted ids that don't
        belong to any of the avis's contacts. Result is the empty list
        — the orchestrator's `if not filtered_ids: return 0` short-
        circuits before any DB read or email."""
        assert filter_allowed_recipients([99, 100], {1, 2, 3}) == []

    def test_preserves_input_order(self) -> None:
        """Order matters : the orchestrator increments
        `justificatif_notifications_count` per accepted recipient, so
        the iteration order shows up in the audit trail."""
        result = filter_allowed_recipients([5, 1, 3, 2, 4], {1, 2, 3, 4, 5})
        assert result == [5, 1, 3, 2, 4]

    def test_preserves_duplicates_in_input(self) -> None:
        """Duplicates in `recipient_user_ids` (a buggy client could
        send the same id twice) are preserved. The orchestrator's
        `db.session.get(User, id)` is idempotent so the worst case
        is one extra notification — but we DON'T silently dedup
        here, that's a caller responsibility."""
        result = filter_allowed_recipients([1, 1, 2], {1, 2})
        assert result == [1, 1, 2]

    def test_empty_input_returns_empty_list(self) -> None:
        assert filter_allowed_recipients([], {1, 2, 3}) == []

    def test_empty_allowed_set_returns_empty_list(self) -> None:
        """No contacts on the avis → everything is unauthorised."""
        assert filter_allowed_recipients([1, 2, 3], set()) == []


# ----------------------------------------------------------------------
# resolve_media_name
# ----------------------------------------------------------------------


class TestResolveMediaName:
    """`resolve_media_name` picks the display name shown to the
    participant.

    Order of preference :
        1. `org.bw_name` (BusinessWall-synced public brand)
        2. `org.name` (raw legal org name)
        3. em-dash fallback (`"—"`)

    A regression here would email participants with a blank media
    name (downstream templates render verbatim)."""

    def test_returns_bw_name_when_present(self) -> None:
        """`bw_name` wins over `name` — it's the brand the journalist
        chose to display on AiPRESS24."""
        org = _OrgLike(bw_name="Le Monde Tech", name="LMT SARL")
        assert resolve_media_name(org) == "Le Monde Tech"

    def test_falls_back_to_name_when_bw_name_empty(self) -> None:
        """KYC-incomplete org : no BW yet, but a legal name. Use the
        legal name rather than dropping to em-dash."""
        org = _OrgLike(bw_name="", name="LMT SARL")
        assert resolve_media_name(org) == "LMT SARL"

    def test_returns_em_dash_when_both_names_empty(self) -> None:
        """Both fields empty → the placeholder em-dash. An empty
        string would leak into the email body."""
        org = _OrgLike(bw_name="", name="")
        assert resolve_media_name(org) == EM_DASH_FALLBACK

    def test_returns_em_dash_when_org_is_none(self) -> None:
        """No organisation at all (freelance journalist) → em-dash.
        Must NOT raise."""
        assert resolve_media_name(None) == EM_DASH_FALLBACK

    def test_em_dash_fallback_constant(self) -> None:
        """Pin the exact code point — a future copy refactor might
        try to "normalise" the em-dash to a hyphen."""
        assert EM_DASH_FALLBACK == "—"

    def test_handles_org_without_bw_name_attr(self) -> None:
        """`getattr(org, "bw_name", None)` — an org partial object
        without the attribute at all (legacy migration row) still
        works."""
        org = SimpleNamespace(name="LegacyOrg")
        assert resolve_media_name(org) == "LegacyOrg"

    def test_handles_org_without_any_name_attrs(self) -> None:
        """Both `bw_name` and `name` attributes absent → em-dash.
        Pinned so a broken model doesn't crash the mail batch."""
        org = SimpleNamespace()
        assert resolve_media_name(org) == EM_DASH_FALLBACK

    @pytest.mark.parametrize(
        ("bw_name", "name", "expected"),
        [
            ("BW Brand", "Legal Name", "BW Brand"),
            ("", "Legal Name", "Legal Name"),
            ("", "", "—"),
            ("BW Only", "", "BW Only"),
        ],
    )
    def test_preference_table(self, bw_name: str, name: str, expected: str) -> None:
        """Parametric pin of the (bw_name, name) → display-name
        table. A change to the precedence order trips a row."""
        assert resolve_media_name(_OrgLike(bw_name=bw_name, name=name)) == expected


# ----------------------------------------------------------------------
# build_in_app_message
# ----------------------------------------------------------------------


class TestBuildInAppMessage:
    """`build_in_app_message` renders the cloche body. French copy
    is product-visible — pin to prevent a careless rewrite."""

    def test_embeds_journalist_name_and_article_title(self) -> None:
        msg = build_in_app_message("Bob Journalist", "L'IA dans la presse")
        assert "Bob Journalist" in msg
        assert "L'IA dans la presse" in msg

    def test_uses_french_guillemets_around_article_title(self) -> None:
        """French guillemets « … » are part of the product copy.
        Pin them so a "normalise quotes" refactor doesn't silently
        replace them with ASCII double quotes."""
        msg = build_in_app_message("Bob", "Some Article")
        assert "«" in msg
        assert "»" in msg
        assert "« Some Article »" in msg

    def test_mentions_participation_context(self) -> None:
        """The message must tell the participant WHY they're being
        notified — that an article was published « suite à votre
        participation »."""
        msg = build_in_app_message("Bob", "X")
        assert "participation" in msg

    def test_exact_message_shape(self) -> None:
        """Pin the full string shape — a one-character drift trips
        this test, making the regression auditable."""
        msg = build_in_app_message("Bob", "Titre")
        assert msg == (
            "Bob a publié un article suite à votre participation : « Titre »."
        )

    def test_empty_strings_dont_crash(self) -> None:
        """An empty journalist name or article title (corrupt row)
        must NOT raise — the orchestrator already swallows mail/cloche
        failures, but the message build itself should be total."""
        assert build_in_app_message("", "") == (
            " a publié un article suite à votre participation : «  »."
        )


# ----------------------------------------------------------------------
# build_mail_kwargs
# ----------------------------------------------------------------------


class TestBuildMailKwargs:
    """`build_mail_kwargs` maps call-site args onto the
    `JustificatifInvitationMail` constructor kwargs. The mapping IS
    the contract — a swap silently corrupts every participant email."""

    def test_full_field_mapping(self) -> None:
        """Pin every field. The list-and-each-key assertions catch
        both a missing key (KeyError downstream) and a swapped value."""
        kwargs = build_mail_kwargs(
            recipient=_UserLike(
                full_name="Alice Expert",
                email="alice@example.com",
            ),
            article=_ArticleLike(title="Titre Article"),
            avis_enquete=_AvisLike(titre="Enquête sur la presse"),
            journalist=_UserLike(
                full_name="Bob Journalist",
                email="bob@example.com",
            ),
            media_name="Le Monde Tech",
            article_url="https://aipress24.com/wire/99",
        )
        assert kwargs == {
            "sender": "contact@aipress24.com",
            "recipient": "alice@example.com",
            "sender_mail": "bob@example.com",
            "recipient_full_name": "Alice Expert",
            "enquete_title": "Enquête sur la presse",
            "journalist_full_name": "Bob Journalist",
            "media_name": "Le Monde Tech",
            "article_title": "Titre Article",
            "article_url": "https://aipress24.com/wire/99",
        }

    def test_default_sender_email_constant(self) -> None:
        """Pin the constant : the contact address is the AiPRESS24
        SMTP-allowed `From:` ; a custom address would bounce."""
        assert DEFAULT_SENDER_EMAIL == "contact@aipress24.com"

    def test_journalist_without_email_falls_back_to_contact_address(
        self,
    ) -> None:
        """KYC-incomplete journalist : `journalist.email == ""` →
        `sender_mail` defaults to the contact address rather than
        an empty `From:` header (which makes SMTP bounce)."""
        kwargs = build_mail_kwargs(
            recipient=_UserLike(email="alice@example.com"),
            article=_ArticleLike(),
            avis_enquete=_AvisLike(),
            journalist=_UserLike(email=""),
            media_name="X",
            article_url="/x",
        )
        assert kwargs["sender_mail"] == DEFAULT_SENDER_EMAIL

    def test_recipient_email_none_routes_to_empty_string(self) -> None:
        """Recipient with no email → empty string (mailer drops it).
        Must NOT crash with TypeError on `None.strip()`."""

        class _NoEmailUser:
            email = None
            full_name = "X"

        kwargs = build_mail_kwargs(
            recipient=_NoEmailUser(),  # type: ignore[arg-type]
            article=_ArticleLike(),
            avis_enquete=_AvisLike(),
            journalist=_UserLike(),
            media_name="X",
            article_url="/x",
        )
        assert kwargs["recipient"] == ""

    def test_empty_enquete_title_defaults_to_em_dash(self) -> None:
        """`avis_enquete.titre == ""` (nullable column) → em-dash
        rather than a blank line in the email body."""
        kwargs = build_mail_kwargs(
            recipient=_UserLike(),
            article=_ArticleLike(),
            avis_enquete=_AvisLike(titre=""),
            journalist=_UserLike(),
            media_name="X",
            article_url="/x",
        )
        assert kwargs["enquete_title"] == EM_DASH_FALLBACK

    def test_avis_missing_titre_attr_defaults_to_em_dash(self) -> None:
        """`getattr(avis_enquete, "titre", "")` — an avis row whose
        `titre` attribute is absent (legacy partial row, test fake)
        still produces a valid mail rather than crashing."""
        avis = SimpleNamespace()  # no `titre` attribute
        kwargs = build_mail_kwargs(
            recipient=_UserLike(),
            article=_ArticleLike(),
            avis_enquete=avis,  # type: ignore[arg-type]
            journalist=_UserLike(),
            media_name="X",
            article_url="/x",
        )
        assert kwargs["enquete_title"] == EM_DASH_FALLBACK

    def test_article_url_passes_through_unchanged(self) -> None:
        """URL is opaque — `build_mail_kwargs` must NOT try to
        normalise / strip / encode it. The orchestrator built it via
        `_absolute_url_for`, the helper just forwards."""
        url = "https://aipress24.com/wire/99?ref=just&utm=x"
        kwargs = build_mail_kwargs(
            recipient=_UserLike(),
            article=_ArticleLike(),
            avis_enquete=_AvisLike(),
            journalist=_UserLike(),
            media_name="X",
            article_url=url,
        )
        assert kwargs["article_url"] == url

    def test_media_name_passes_through_unchanged(self) -> None:
        """The caller already resolved `media_name` via
        `resolve_media_name` (incl. em-dash fallback). `build_mail_
        kwargs` is a dumb forwarder — pin so it doesn't sneak in a
        second fallback."""
        kwargs = build_mail_kwargs(
            recipient=_UserLike(),
            article=_ArticleLike(),
            avis_enquete=_AvisLike(),
            journalist=_UserLike(),
            media_name=EM_DASH_FALLBACK,
            article_url="/x",
        )
        assert kwargs["media_name"] == EM_DASH_FALLBACK


# ----------------------------------------------------------------------
# next_notification_count
# ----------------------------------------------------------------------


class TestNextNotificationCount:
    """`next_notification_count` centralises the `None → 0` default +
    addition for `AvisEnquete.justificatif_notifications_count`.
    Downstream rémunération is computed off this counter — a drift
    in defaulting silently affects payouts."""

    def test_adds_delta_to_existing_count(self) -> None:
        assert next_notification_count(3, 2) == 5

    def test_treats_none_as_zero(self) -> None:
        """A freshly-created `AvisEnquete` may have a NULL counter
        before the first notification batch — must be treated as 0."""
        assert next_notification_count(None, 4) == 4

    def test_treats_zero_as_zero(self) -> None:
        """A counter explicitly set to 0 (not NULL) must NOT be
        bumped to 1 by the `or 0` truth-test trick — pin the
        addition."""
        assert next_notification_count(0, 3) == 3

    def test_delta_zero_is_identity(self) -> None:
        """A no-op call (all recipients filtered out) returns the
        current value unchanged. The orchestrator's
        `if notified:` guard already short-circuits, but defence
        in depth doesn't hurt."""
        assert next_notification_count(7, 0) == 7

    @pytest.mark.parametrize(
        ("current", "delta", "expected"),
        [
            (None, 0, 0),
            (None, 1, 1),
            (0, 0, 0),
            (0, 5, 5),
            (10, 1, 11),
            (10, 10, 20),
        ],
    )
    def test_parametric_table(
        self, current: int | None, delta: int, expected: int
    ) -> None:
        assert next_notification_count(current, delta) == expected
