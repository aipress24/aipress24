# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Mock-free unit tests for the pure helpers in
`app.modules.wip.views.opportunities`.

The view module mixes Flask request handling, repository lookups and
template rendering — none of which is appropriate for a unit test.
However, several pure pieces sit inside the same file :

- protocol-from-domain picking (loopback vs everything else),
- absolute-URL composition for outbound email/notification links,
- the response-label translator used in the journalist email,
- press-officer email selection from a validated list,
- the default-form-state derivation from a contact's `StatutAvis`,
- the marketplace tab → (label, endpoint) dispatch table.

These were extracted from the view body so they can be exercised
directly with plain values — no stand-in test doubles, no Flask app
context. The integration coverage for the imperative shell (DB
writes, request parsing, redirects) lives in
`tests/c_e2e/modules/wip/test_opportunities_views.py`.
"""

from __future__ import annotations

import pytest

from app.modules.wip.views.opportunities import (
    _MARKETPLACE_TAB_LABELS,
    _OPPORTUNITES_TABS,
    _STATUS_TO_FORM_FIELD,
    _build_absolute_url,
    _form_defaults_from_status,
    _marketplace_labels,
    _pick_protocol,
    _select_press_officer_email,
    _translate_response_label,
)


class TestPickProtocol:
    """`_pick_protocol` is the loopback-vs-TLS switch used by every
    absolute-URL builder in the file. Picking the wrong protocol
    breaks email links in dev (https on 127.0.0.1) or production
    (http on a public domain), so the rule is simple but
    load-bearing."""

    @pytest.mark.parametrize(
        "domain",
        [
            "127.0.0.1",
            "127.0.0.1:5000",
            "127.1.2.3",
        ],
    )
    def test_loopback_addresses_get_http(self, domain: str) -> None:
        assert _pick_protocol(domain) == "http"

    @pytest.mark.parametrize(
        "domain",
        [
            "aipress24.com",
            "staging.aipress24.com",
            "localhost",
            "localhost:5000",
            "192.168.1.10",
        ],
    )
    def test_non_loopback_addresses_get_https(self, domain: str) -> None:
        assert _pick_protocol(domain) == "https"


class TestBuildAbsoluteUrl:
    """`_build_absolute_url` composes the link travelling in outbound
    notification emails. Format is `<proto>://<domain><path>`."""

    def test_https_for_public_domain(self) -> None:
        url = _build_absolute_url("aipress24.com", "/wip/opportunities/42")
        assert url == "https://aipress24.com/wip/opportunities/42"

    def test_http_for_loopback(self) -> None:
        url = _build_absolute_url("127.0.0.1:5000", "/wip/opportunities/7")
        assert url == "http://127.0.0.1:5000/wip/opportunities/7"

    def test_path_kept_verbatim(self) -> None:
        # No accidental rewriting / stripping of the path component.
        url = _build_absolute_url("example.com", "/a/b/c?x=1&y=2")
        assert url == "https://example.com/a/b/c?x=1&y=2"


class TestTranslateResponseLabel:
    """The journalist notification email gets a human label, not a raw
    form token. Only `oui_relation_presse` is rewritten — all other
    tokens flow through unchanged so the email reflects the actual
    response verbatim."""

    def test_oui_relation_presse_translated(self) -> None:
        assert (
            _translate_response_label("oui_relation_presse")
            == "oui, avec relation presse"
        )

    @pytest.mark.parametrize(
        "raw",
        ["oui", "non", "non-mais", "", "anything-else"],
    )
    def test_other_tokens_passthrough(self, raw: str) -> None:
        assert _translate_response_label(raw) == raw


class TestSelectPressOfficerEmail:
    """Bug #0075/2 logic : when the form rendered a dropdown, the
    user's pick is trusted only if validated. Falls back to the first
    valid email otherwise, or empty when no valid email is known.
    This guards against POST tampering while preserving the
    single-option case where the form omits the field."""

    def test_picked_present_in_valid_set_is_returned(self) -> None:
        out = _select_press_officer_email("b@x.com", ["a@x.com", "b@x.com", "c@x.com"])
        assert out == "b@x.com"

    def test_picked_not_in_valid_set_falls_back_to_first(self) -> None:
        # Tampered POST : reject the picked address, fall back.
        out = _select_press_officer_email("evil@attacker", ["a@x.com", "b@x.com"])
        assert out == "a@x.com"

    def test_empty_pick_falls_back_to_first_valid(self) -> None:
        # Single-option case — form didn't render a dropdown.
        out = _select_press_officer_email("", ["only@x.com"])
        assert out == "only@x.com"

    def test_whitespace_only_pick_treated_as_empty(self) -> None:
        out = _select_press_officer_email("   ", ["only@x.com"])
        assert out == "only@x.com"

    def test_picked_is_stripped_before_match(self) -> None:
        out = _select_press_officer_email("  b@x.com  ", ["a@x.com", "b@x.com"])
        assert out == "b@x.com"

    def test_empty_pick_and_no_valid_emails_returns_empty(self) -> None:
        assert _select_press_officer_email("", []) == ""

    def test_invalid_pick_and_no_valid_emails_returns_empty(self) -> None:
        assert _select_press_officer_email("foo@bar", []) == ""


class TestFormDefaultsFromStatus:
    """`_form_defaults_from_status` derives the form prefill values
    from a contact's persisted status + free-text notes. The pure
    helper returns a complete dict with the four prefill keys —
    exactly one of the three text fields is populated for an
    answered status, all empty for `EN_ATTENTE` / unknown."""

    def test_en_attente_returns_all_empty(self) -> None:
        out = _form_defaults_from_status("en_attente", "ignored")
        assert out == {
            "reponse1": "",
            "contribution": "",
            "refusal_reason": "",
            "suggestion": "",
        }

    def test_unknown_status_returns_all_empty(self) -> None:
        out = _form_defaults_from_status("not-a-status", "x")
        assert out == {
            "reponse1": "",
            "contribution": "",
            "refusal_reason": "",
            "suggestion": "",
        }

    def test_accepte_prefills_contribution(self) -> None:
        out = _form_defaults_from_status("accepte", "I can do it")
        assert out == {
            "reponse1": "oui",
            "contribution": "I can do it",
            "refusal_reason": "",
            "suggestion": "",
        }

    def test_accepte_relation_presse_prefills_contribution(self) -> None:
        out = _form_defaults_from_status(
            "accepte_relation_presse", "ask the PR officer"
        )
        assert out == {
            "reponse1": "oui_relation_presse",
            "contribution": "ask the PR officer",
            "refusal_reason": "",
            "suggestion": "",
        }

    def test_refuse_prefills_refusal_reason(self) -> None:
        out = _form_defaults_from_status("refuse", "no time")
        assert out == {
            "reponse1": "non",
            "contribution": "",
            "refusal_reason": "no time",
            "suggestion": "",
        }

    def test_refuse_suggestion_prefills_suggestion(self) -> None:
        out = _form_defaults_from_status("refuse_suggestion", "ask Alice")
        assert out == {
            "reponse1": "non-mais",
            "contribution": "",
            "refusal_reason": "",
            "suggestion": "ask Alice",
        }

    @pytest.mark.parametrize(
        "status",
        ["accepte", "accepte_relation_presse", "refuse", "refuse_suggestion"],
    )
    def test_empty_notes_keep_all_prefills_empty(self, status: str) -> None:
        # Empty notes should keep the text fields empty but still set
        # the matching `reponse1` token so the radio button is
        # rendered as selected.
        out = _form_defaults_from_status(status, "")
        assert out["reponse1"] != ""
        assert out["contribution"] == ""
        assert out["refusal_reason"] == ""
        assert out["suggestion"] == ""

    def test_helper_matches_status_dispatch_table(self) -> None:
        # Guard : every status in the dispatch table must yield a
        # non-empty `reponse1`, and exactly one text field must be
        # populated when notes are present. This catches accidental
        # additions to `_STATUS_TO_FORM_FIELD` that forget either
        # half of the mapping.
        for status in _STATUS_TO_FORM_FIELD:
            out = _form_defaults_from_status(status, "some-note")
            assert out["reponse1"] != ""
            non_empty_text_fields = [
                k for k in ("contribution", "refusal_reason", "suggestion") if out[k]
            ]
            assert non_empty_text_fields == [_STATUS_TO_FORM_FIELD[status][1]]


class TestMarketplaceLabels:
    """The marketplace tab dispatch maps a tab id to (human label,
    biz detail endpoint name). The endpoint name is then concatenated
    with the `biz.` prefix at the call site. Drift here would break
    the « View details » links on every marketplace candidacy row."""

    @pytest.mark.parametrize(
        ("tab", "expected"),
        [
            ("missions", ("Mission", "missions_detail")),
            ("projects", ("Projet", "projects_detail")),
            ("jobs", ("Emploi", "jobs_detail")),
        ],
    )
    def test_known_tabs(self, tab: str, expected: tuple[str, str]) -> None:
        assert _marketplace_labels(tab) == expected

    def test_unknown_tab_raises_keyerror(self) -> None:
        with pytest.raises(KeyError):
            _marketplace_labels("unknown")

    def test_dispatch_table_covers_marketplace_tabs_only(self) -> None:
        # The four `_OPPORTUNITES_TABS` are (avis + 3 marketplace).
        # The marketplace dispatch table should cover exactly the 3
        # marketplace tabs — `avis` is handled by a different code
        # path and must NOT appear here.
        all_tab_ids = {tab_id for tab_id, _ in _OPPORTUNITES_TABS}
        assert set(_MARKETPLACE_TAB_LABELS) == all_tab_ids - {"avis"}


class TestOpportunitesTabsConstant:
    """The `_OPPORTUNITES_TABS` tuple drives the navigation strip at
    the top of the page. Order + labels are visible to end users."""

    def test_tab_ids_in_expected_order(self) -> None:
        ids = [tab_id for tab_id, _ in _OPPORTUNITES_TABS]
        assert ids == ["avis", "missions", "projects", "jobs"]

    def test_labels_are_french_strings(self) -> None:
        # Defensive : labels are user-facing French copy.
        labels = [label for _, label in _OPPORTUNITES_TABS]
        assert labels == ["Avis d'enquête", "Missions", "Projets", "Emplois"]

    def test_tab_ids_are_unique(self) -> None:
        ids = [tab_id for tab_id, _ in _OPPORTUNITES_TABS]
        assert len(set(ids)) == len(ids)
