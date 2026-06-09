# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `MaskFields` in `app.modules.swork.masked_fields`.

`MaskFields` is the accumulator passed through the privacy-filtering
chain. Each step of `filter_email_mobile` adds masked fields and a
human-readable « story » line explaining why the field was hidden,
so an admin can debug the visibility logic without re-reading the
code.

This is a small value-collector class but it underpins the whole
privacy-filter contract — every Member-page request runs through
it. Pinning its semantics makes regressions in
`filter_email_mobile` (which is one of the more complex permission
functions in the codebase) easier to track.
"""

from __future__ import annotations

from app.modules.swork.masked_fields import MaskFields


class TestMaskFieldsInit:
    def test_starts_empty(self):
        """A fresh `MaskFields` is empty : no masked fields, no
        story. Pin so a future « pre-populate from defaults »
        refactor surfaces explicitly."""
        mf = MaskFields()
        assert mf.masked == set()
        assert mf.story == ""

    def test_masked_is_a_set(self):
        """Pin the set semantics — duplicates collapse, ordering
        doesn't matter. A future list refactor would silently
        introduce both."""
        mf = MaskFields()
        assert isinstance(mf.masked, set)


class TestAddField:
    def test_add_single_field(self):
        mf = MaskFields()
        mf.add_field("email")
        assert mf.masked == {"email"}

    def test_add_multiple_fields(self):
        mf = MaskFields()
        mf.add_field("email")
        mf.add_field("mobile")
        assert mf.masked == {"email", "mobile"}

    def test_add_duplicate_is_idempotent(self):
        """Adding the same field twice yields one entry — set
        semantics. Pin so a future list refactor doesn't introduce
        duplicates."""
        mf = MaskFields()
        mf.add_field("email")
        mf.add_field("email")
        assert mf.masked == {"email"}

    def test_field_names_kept_verbatim(self):
        """No case-folding, no normalisation. Pin the verbatim
        contract — the downstream template iterates `mf.masked`
        and compares against literal field names."""
        mf = MaskFields()
        mf.add_field("Email")  # capital E
        mf.add_field("email")  # lowercase
        # Both stored as distinct entries.
        assert mf.masked == {"Email", "email"}


class TestRemoveField:
    def test_remove_existing_field(self):
        mf = MaskFields()
        mf.add_field("email")
        mf.add_field("mobile")
        mf.remove_field("email")
        assert mf.masked == {"mobile"}

    def test_remove_non_existing_field_silently(self):
        """`discard`-style removal : no error if the field wasn't
        masked in the first place. Pin so a regression to `set.remove`
        (which raises) doesn't surface unexpectedly at runtime."""
        mf = MaskFields()
        mf.add_field("email")
        # Should not raise.
        mf.remove_field("never-added")
        assert mf.masked == {"email"}

    def test_remove_from_empty(self):
        """Removing from empty doesn't raise."""
        mf = MaskFields()
        mf.remove_field("anything")
        assert mf.masked == set()


class TestAddMessage:
    """The « story » is appended-to comma-separated reasoning trail.
    It powers the `mf.story` debug string that surfaces in admin
    panels when a field-visibility decision is in question."""

    def test_single_message(self):
        mf = MaskFields()
        mf.add_message("email not allowed for PRESSE")
        assert mf.story == "email not allowed for PRESSE"

    def test_multiple_messages_comma_separated(self):
        r"""Pin the separator — a future « \n » or « ; » regression
        would break the admin panel's single-line layout."""
        mf = MaskFields()
        mf.add_message("first reason")
        mf.add_message("second reason")
        assert mf.story == "first reason, second reason"

    def test_empty_message_appended(self):
        """An empty message still adds a separator (defensive case ;
        pin to document the behaviour)."""
        mf = MaskFields()
        mf.add_message("first")
        mf.add_message("")
        assert mf.story == "first, "

    def test_message_with_existing_story_appends(self):
        """The « if self.story » check skips the separator only on
        the first append. Pin so a `, ` doesn't appear at the start
        of the story string."""
        mf = MaskFields()
        assert mf.story == ""
        mf.add_message("only")
        assert mf.story == "only"
        assert not mf.story.startswith(",")


class TestMaskFieldsIntegration:
    """Cross-checks : the typical use pattern in
    `filter_email_mobile` is to add fields + messages together."""

    def test_typical_chain(self):
        mf = MaskFields()
        mf.add_field("email")
        mf.add_message("email not allowed for PRESSE")
        mf.add_field("mobile")
        mf.add_message("mobile not allowed for PRESSE")
        mf.remove_field("email")
        mf.add_message("email: allowed because followee")
        assert mf.masked == {"mobile"}
        assert "followee" in mf.story
        assert "not allowed for PRESSE" in mf.story

    def test_truthy_when_anything_masked(self):
        """Pin so the existing `if not mask_fields.masked:` checks
        in `filter_email_mobile` keep working — empty set is
        falsy, non-empty is truthy."""
        mf = MaskFields()
        assert not mf.masked
        mf.add_field("email")
        assert mf.masked
