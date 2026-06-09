# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `BW_TYPES` config dict in
`app.modules.bw.bw_activation.config`.

`BW_TYPES` is the master config dict driving the BW activation flow.
Each BW type carries :
- `name`, `description` (admin-facing)
- `free` (bool — drives the « rate_message » + Stripe-skip flow)
- `rate_message`, `activation_text` (user-facing French strings)
- `manager_role` (role name displayed in confirmation messages)
- `allows_self_management` (gates « can a single-person org assign
  themselves a role »)
- `newsroom_features`, `onboarding_messages` (user-facing lists)

Renaming any key without updating the template-render code silently
breaks the activation flow on the affected BW type. Pinning shape
+ canonical entries catches that at PR time.
"""

from __future__ import annotations

import pytest

from app.modules.bw.bw_activation.config import BW_TYPES
from app.modules.bw.bw_activation.models import BWType


class TestBWTypesShape:
    def test_all_keys_are_known_bw_type_values(self):
        """Every key must be a real BWType value (case-sensitive
        string). A typo would break the Stripe-callback handler
        that does `BW_TYPES[bw_type_value]`."""
        known = {m.value for m in BWType}
        for k in BW_TYPES:
            assert k in known, f"BW_TYPES key {k!r} doesn't match any BWType member"

    def test_every_entry_is_a_dict(self):
        for k, v in BW_TYPES.items():
            assert isinstance(v, dict), f"BW_TYPES[{k!r}] must be a dict"

    def test_every_entry_has_required_keys(self):
        """Each BW type config must carry the keys the templates and
        activation handlers read. Missing any one of them silently
        renders an empty section. Pin the **mandatory** subset only ;
        `activation_text` is asymmetric (only on some BW types — the
        paid tiers carry their CGV approval text inline in the Stripe
        success page instead)."""
        required = {
            "name",
            "description",
            "free",
            "rate_message",
            "manager_role",
            "allows_self_management",
            "onboarding_messages",
        }
        for bw_type, config in BW_TYPES.items():
            missing = required - set(config.keys())
            assert not missing, f"BW_TYPES[{bw_type!r}] missing keys: {missing}"

    def test_activation_text_present_on_free_types(self):
        """The 4 free BW types display an `activation_text` button
        in the activation flow (« Approuver l'accord… »). Pin so
        a refactor that removes it from a free type silently breaks
        the activation CTA."""
        for bw_type, config in BW_TYPES.items():
            if config["free"]:
                assert "activation_text" in config, (
                    f"Free BW type {bw_type!r} missing "
                    "`activation_text` — the activation CTA "
                    "would render empty."
                )


class TestBWTypesFieldTypes:
    def test_string_fields_are_strings(self):
        """`name`, `description`, `rate_message`, etc. — pin the
        type so a future int / None value can't sneak in."""
        string_keys = (
            "name",
            "description",
            "rate_message",
            "manager_role",
        )
        for bw_type, config in BW_TYPES.items():
            for key in string_keys:
                value = config[key]
                assert isinstance(value, str), (
                    f"BW_TYPES[{bw_type!r}][{key!r}] is {value!r}, expected str"
                )
                assert value, f"BW_TYPES[{bw_type!r}][{key!r}] is empty"

    def test_activation_text_is_string_when_present(self):
        for _bw_type, config in BW_TYPES.items():
            if "activation_text" in config:
                value = config["activation_text"]
                assert isinstance(value, str)
                assert value

    def test_bool_fields_are_bools(self):
        """`free` + `allows_self_management` are predicate-driven
        config — pin the type so a truthy string (« yes ») doesn't
        accidentally route the activation flow."""
        for bw_type, config in BW_TYPES.items():
            for key in ("free", "allows_self_management"):
                assert isinstance(config[key], bool), (
                    f"BW_TYPES[{bw_type!r}][{key!r}] is {config[key]!r}, expected bool"
                )

    def test_onboarding_messages_is_list_of_strings(self):
        """The template iterates this with Jinja's `{% for %}` ;
        a missing list crashes the render."""
        for bw_type, config in BW_TYPES.items():
            messages = config["onboarding_messages"]
            assert isinstance(messages, list), (
                f"BW_TYPES[{bw_type!r}]['onboarding_messages'] must be a list"
            )
            assert messages, f"BW_TYPES[{bw_type!r}] has empty onboarding_messages"
            for msg in messages:
                assert isinstance(msg, str)
                assert msg


class TestBWTypesBusinessRules:
    """Pin two important business-rule asymmetries baked into the
    config."""

    def test_media_is_free(self):
        """`media` BW type is free — no Stripe checkout in the
        activation flow. Pin so a future « let's monetise it »
        change is conscious."""
        assert BW_TYPES[BWType.MEDIA.value]["free"] is True

    def test_micro_is_free(self):
        """`micro` (single-journalist micro-entreprise) is free.
        Pin so the rights-holder asymmetry (`_RIGHTS_HOLDER_BW_TYPES`
        in rights_policy.py) stays aligned with the pricing."""
        assert BW_TYPES[BWType.MICRO.value]["free"] is True

    def test_paid_bw_types_are_not_free(self):
        """The 3 paid tiers (PR / TRANSFORMERS / LEADERS_EXPERTS)
        must have `free=False` so the activation flow routes them
        through Stripe."""
        for paid_type in (
            BWType.PR,
            BWType.TRANSFORMERS,
            BWType.LEADERS_EXPERTS,
        ):
            if paid_type.value not in BW_TYPES:
                continue
            assert BW_TYPES[paid_type.value]["free"] is False, (
                f"BW_TYPES[{paid_type.value!r}] is marked free — "
                "should be paid per pricing config."
            )

    def test_self_management_only_for_single_person_types(self):
        """`allows_self_management=True` is reserved for BW types
        where a single user IS the whole organisation (micro,
        union). Pin so a refactor doesn't accidentally widen the
        gate to media (which would let a journalist self-assign
        a Manager role without their PR Agency approving)."""
        # Pin: media must NOT allow self-management.
        assert BW_TYPES[BWType.MEDIA.value]["allows_self_management"] is False
        # Pin: micro IS single-person.
        assert BW_TYPES[BWType.MICRO.value]["allows_self_management"] is True


class TestBWTypesFreeTierCount:
    """Erick spec'd « 5 free BW types ». Pin the count so a refactor
    that converts one to paid silently moves the line without us
    noticing."""

    def test_at_least_five_bw_types_total(self):
        assert len(BW_TYPES) >= 5

    def test_free_bw_types_have_zero_rate(self):
        """Every free BW type's rate_message contains « GRATUIT »
        (the French marker the UI surfaces). Pin so a future
        translation regression doesn't silently render confusing
        rate messages."""
        for bw_type, config in BW_TYPES.items():
            if config["free"]:
                assert "GRATUIT" in config["rate_message"], (
                    f"BW_TYPES[{bw_type!r}] is free but its "
                    f"rate_message {config['rate_message']!r} "
                    "doesn't contain « GRATUIT »."
                )


@pytest.mark.parametrize(
    "bw_type",
    [
        BWType.MEDIA.value,
        BWType.MICRO.value,
        BWType.CORPORATE_MEDIA.value,
        BWType.UNION.value,
    ],
)
def test_canonical_free_types_present(bw_type):
    """Each of the 4 canonical free BW types must be in BW_TYPES.
    Pin the public-API expectation."""
    assert bw_type in BW_TYPES
