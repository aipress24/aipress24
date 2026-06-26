# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Stage 2: Contact nomination routes."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, cast

from flask import redirect, render_template, request, session, url_for

from app.modules.bw.bw_activation import bp
from app.modules.bw.bw_activation.config import BW_TYPES
from app.modules.bw.bw_activation.user_utils import StdDict, get_current_user_data

if TYPE_CHECKING:
    pass


# Fields shared by the owner and payer halves of the stage-2 form.
_CONTACT_FIELDS: tuple[str, ...] = ("first_name", "last_name", "email", "phone")


def parse_contacts_form(form: Mapping[str, str | None]) -> dict[str, str | None]:
    """Pure: extract owner / payer contact values from a form mapping.

    The stage-2 POST handler stores eight session keys (owner_* and
    payer_*) and copies the owner block over the payer block when the
    "same_as_owner" checkbox is on. Lifted as a pure helper so the
    duplication / passthrough rule can be exercised without a Flask
    request — the route then writes the returned dict straight into
    `session`.

    Args:
        form: Mapping of form field names to values (e.g. ``request.form``
            or a plain dict in tests). Missing keys are treated as
            ``None`` (which is what ``MultiDict.get`` returns).

    Returns:
        A dict with eight keys: ``owner_first_name`` … ``payer_phone``.
        When the form contains ``same_as_owner == "on"`` the payer
        values are taken from the owner values (regardless of any
        payer_* fields the user might have submitted).
    """
    result: dict[str, str | None] = {}
    for field in _CONTACT_FIELDS:
        result[f"owner_{field}"] = form.get(f"owner_{field}")

    same_as_owner = form.get("same_as_owner") == "on"
    for field in _CONTACT_FIELDS:
        if same_as_owner:
            result[f"payer_{field}"] = result[f"owner_{field}"]
        else:
            result[f"payer_{field}"] = form.get(f"payer_{field}")
    return result


def post_contacts_redirect_endpoint(bw_type: str) -> str:
    """Pure: decide which endpoint to redirect to after submit_contacts.

    All BW types now land on the pricing page; free types use a €0
    Stripe subscription and skip the quantity input. Extracted from
    `submit_contacts` so the dispatch rule can be pinned without
    spinning up the Flask app.

    Raises:
        KeyError: if `bw_type` is not a known BW type — the route only
            calls this after writing `bw_type` to session via
            `select_subscription`, which validates against `BW_TYPES`.
    """
    if bw_type not in BW_TYPES:
        raise KeyError(bw_type)
    return "bw_activation.pricing_page"


@bp.route("/nominate-contacts")
def nominate_contacts():
    """Step 2: Nominate Business Wall Owner and Paying Party."""
    if not session.get("bw_type_confirmed"):
        return redirect(url_for("bw_activation.confirm_subscription"))

    bw_type: str = cast(str, session.get("bw_type"))
    bw_info: dict[str, Any] = BW_TYPES.get(bw_type, {})

    owner_data: StdDict = get_current_user_data()

    return render_template(
        "bw_activation/02_nominate_contacts.html",
        bw_type=bw_type,
        bw_info=bw_info,
        owner_data=owner_data,
    )


@bp.route("/submit-contacts", methods=["POST"])
def submit_contacts():
    """Process contacts nomination and redirect to activation."""
    if not session.get("bw_type_confirmed"):
        return redirect(url_for("bw_activation.confirm_subscription"))

    # Store contact information in session via the pure parser so the
    # same-as-owner duplication rule stays unit-testable.
    parsed = parse_contacts_form(request.form)
    for key, value in parsed.items():
        session[key] = value

    session["contacts_confirmed"] = True

    bw_type: str = cast(str, session.get("bw_type"))
    endpoint = post_contacts_redirect_endpoint(bw_type)
    return redirect(url_for(endpoint, bw_type=bw_type))
