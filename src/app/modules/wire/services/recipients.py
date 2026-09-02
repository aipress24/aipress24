# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Read a hand-typed list of addresses from a form.

Two views each had their own version — article sharing and buying a
gift consultation — and they did not split alike: one accepted spaces as
separators and validated the address shape, the other did not.
"a@b.com c@d.com" therefore meant two recipients on one side and one
invalid string on the other, on a billed path.
"""

from __future__ import annotations


def parse_recipient_emails(raw_emails: str) -> list[str]:
    """Split free-form input into unique, lower-cased addresses.

    Commas, newlines and spaces separate interchangeably: a member who
    pastes a spreadsheet column, a comma-separated list or a line of
    addresses gets the same result.

    Entries that do not look like an address are dropped here rather
    than downstream: this is the boundary, and an invalid address makes
    sense neither for sending nor for billing.
    """
    if not raw_emails:
        return []

    addresses = {
        address
        for token in raw_emails.replace(",", " ").split()
        if _looks_like_an_email(address := token.strip().lower())
    }
    return sorted(addresses)


def _looks_like_an_email(address: str) -> bool:
    """Something, an at-sign, then a dotted domain.

    Nothing more: real validation belongs to the mail server, not to a
    form. But the local part must exist — the previous check accepted
    "@example.com", which would have gone out as a billed recipient.
    """
    local, separator, domain = address.partition("@")
    return bool(separator and local and "." in domain)
