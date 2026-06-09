# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for wip/crud/cbvs/avis_enquete.py.

The CBV is overwhelmingly request-handler orchestration (DB-coupled).
What is pinned here:

- Class-level configuration of `AvisEnqueteWipView`: name, route_base,
  model/repo/table/form wiring, UI labels, and the #0173 frozenset
  `PER_CONTACT_ACTIONS` that allows the journalist *or* expert of a
  contact (regardless of community role) to act on per-contact RDV
  endpoints.
- `AvisEnqueteTable` column shape, action labels and the
  view-namespaced URL prefix that the templates rely on.
- `AvisEnqueteDataSource.get_order_by()` -> orders by `modified_at`
  descending with NULLs last; the CBV deliberately overrides the
  base's `created_at` ordering so freshly edited avis bubble to the
  top of the journalist's list.
- `_parse_rdv_proposal_form` / `_parse_rdv_acceptance_form`: pure
  parsers driven by `request.form`. Cover happy path + every
  defensive ValueError branch and the decline sentinel of the
  acceptance form (the CBV interprets `None` as a refusal).
- `_opportunities_url_builder`: thin absolute-URL wrapper passed to
  `PublicationNotificationService`.
- Module-level Jinja templates `_VOIR_TEMPLATE` / `_MODIFIER_TEMPLATE`:
  they MUST extend `wip/layout/_base.j2` and frame the #0151 step-nav
  bar around the rendered form (top and bottom for "voir", around the
  form for "modifier").

Full request-handling paths (ciblage, notify_publication, rdv_*) are
DB- and session-coupled and are exercised by integration/e2e suites.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from app.modules.wip.crud.cbvs._forms import AvisEnqueteForm
from app.modules.wip.crud.cbvs.avis_enquete import (
    _MODIFIER_TEMPLATE,
    _VOIR_TEMPLATE,
    AvisEnqueteDataSource,
    AvisEnqueteTable,
    AvisEnqueteWipView,
    _opportunities_url_builder,
)
from app.modules.wip.models import (
    AvisEnquete,
    AvisEnqueteRepository,
    RDVType,
)
from app.modules.wip.services.newsroom import RDVAcceptanceData, RDVProposalData

# --------------------------------------------------------------------------- #
# Class-level configuration                                                   #
# --------------------------------------------------------------------------- #


class TestAvisEnqueteWipViewConfig:
    """Pin the public configuration surface of the CBV.

    These values are referenced from templates, blueprints, breadcrumbs
    and the `register_on_app` hook. Any rename here breaks user-facing
    URLs, navigation and the WIP table render. They MUST be stable.
    """

    def test_blueprint_name_and_route_base(self):
        assert AvisEnqueteWipView.name == "avis_enquete"
        assert AvisEnqueteWipView.route_base == "avis-enquete"
        # The path is what the journalist sees in the address bar.
        assert AvisEnqueteWipView.path == "/wip/avis-enquete/"

    def test_wires_the_three_concrete_collaborators(self):
        # The base CBV uses these to fetch the model, instantiate the
        # form and build the listing table. Swapping any of these in
        # the source code must be a deliberate decision.
        assert AvisEnqueteWipView.model_class is AvisEnquete
        assert AvisEnqueteWipView.repo_class is AvisEnqueteRepository
        assert AvisEnqueteWipView.table_class is AvisEnqueteTable
        assert AvisEnqueteWipView.form_class is AvisEnqueteForm

    def test_doc_type_matches_module_slug(self):
        # `doc_type` is the discriminator used by the publication
        # notification + breadcrumb scaffolding.
        assert AvisEnqueteWipView.doc_type == "avis_enquete"

    @pytest.mark.parametrize(
        ("attr", "expected"),
        [
            ("label_main", "Newsroom: Avis d'enquête"),
            ("label_list", "Liste des avis d'enquête"),
            ("label_new", "Créer un avis d'enquête"),
            ("label_edit", "Modifier l'avis d'enquête"),
            ("label_view", "Voir l'avis d'enquête"),
            ("msg_delete_ok", "L'avis d'enquête a été supprimé"),
            (
                "msg_delete_ko",
                "Vous n'êtes pas autorisé à supprimer cet avis d'enquête",
            ),
            ("icon", "newspaper"),
            ("table_id", "avis-enquete-table-body"),
        ],
    )
    def test_ui_strings_are_pinned(self, attr, expected):
        # These strings are surfaced to the journalist; pinning them
        # catches accidental retitling during refactors.
        assert getattr(AvisEnqueteWipView, attr) == expected


class TestPerContactActions:
    """Ticket #0173: per-contact actions authorize on contact party,
    not on community role. The frozenset must be exactly this set,
    nothing more, nothing less.
    """

    def test_exact_set_membership(self):
        actions = AvisEnqueteWipView.PER_CONTACT_ACTIONS
        assert set(actions) == {"rdv_accept", "rdv_details", "rdv_cancel"}
        assert len(actions) == 3

    def test_is_immutable_frozenset(self):
        # Using a `frozenset` rather than a `set` is intentional: it
        # prevents accidental mutation from per-request code.
        assert isinstance(AvisEnqueteWipView.PER_CONTACT_ACTIONS, frozenset)

    @pytest.mark.parametrize("action", ["rdv_accept", "rdv_details", "rdv_cancel"])
    def test_each_known_action_is_a_member(self, action):
        assert action in AvisEnqueteWipView.PER_CONTACT_ACTIONS

    @pytest.mark.parametrize(
        "action",
        # Defensive: actions that look RDV-shaped but require the
        # journalist (rdv_confirm) or are mode-A only (rdv_propose,
        # notify_publication) must NOT bypass the role check.
        ["rdv_confirm", "rdv_propose", "notify_publication", "edit", ""],
    )
    def test_non_listed_actions_are_not_members(self, action):
        assert action not in AvisEnqueteWipView.PER_CONTACT_ACTIONS


# --------------------------------------------------------------------------- #
# Table                                                                       #
# --------------------------------------------------------------------------- #


class TestAvisEnqueteTable:
    """The table drives the WIP listing page; column names and the
    actions menu are part of the user-visible contract.
    """

    def test_table_id_is_pinned(self):
        # Referenced from HTMX swap targets in the template.
        assert AvisEnqueteTable.id == "avis-enquete-table"

    def test_columns_have_expected_names_and_order(self, app):
        with app.test_request_context():
            table = AvisEnqueteTable()
        names = [c["name"] for c in table.get_columns()]
        # Ticket #0195 -- "JdP notifiés" column must be present so the
        # journalist can audit publication-notification counts.
        assert names == [
            "titre",
            "status",
            "justificatif_notifications_count",
            "modified_at",
            "$actions",
        ]

    def test_columns_carry_localised_labels(self, app):
        with app.test_request_context():
            table = AvisEnqueteTable()
        labels = {c["name"]: c["label"] for c in table.get_columns()}
        assert labels["titre"] == "Titre"
        assert labels["status"] == "Statut"
        assert labels["justificatif_notifications_count"] == "JdP notifiés"
        assert labels["modified_at"] == "Modification"

    def test_get_actions_lists_expected_labels(self, app):
        with app.test_request_context():
            table = AvisEnqueteTable()
            actions = table.get_actions(SimpleNamespace(id=42))
        labels = [a["label"] for a in actions]
        assert labels == [
            "Voir",
            "Modifier",
            "Cibler les contacts",
            "Gérer les réponses",
            "Gérer les RDV",
            "Supprimer",
        ]

    def test_url_for_uses_view_namespace(self, app):
        # All listing actions must target the `AvisEnqueteWipView:*`
        # endpoint family so flask_classful's auto-registration works.
        with app.test_request_context():
            table = AvisEnqueteTable()
            url_default = table.url_for(SimpleNamespace(id=7))
            url_edit = table.url_for(SimpleNamespace(id=7), "edit")
        assert "/avis-enquete/" in url_default
        assert url_default.endswith(("/7", "/7/"))
        assert "edit" in url_edit


class TestAvisEnqueteDataSource:
    """The CBV overrides the default `created_at` ordering so that
    a freshly-edited avis appears at the top of the journalist's
    list (the WIP table is sorted by *recency of modification*).
    """

    def test_get_order_by_targets_modified_at_descending_nullslast(self, app):
        with app.test_request_context():
            ds = AvisEnqueteDataSource(model_class=AvisEnquete)
            clause = ds.get_order_by()
        # Compile to a SQL string so we can introspect without
        # depending on SQLAlchemy internals.
        compiled = str(clause)
        assert "modified_at" in compiled
        assert "DESC" in compiled.upper()
        assert "NULL" in compiled.upper()  # NULLS LAST clause


# --------------------------------------------------------------------------- #
# Form parsers (pure given a request context)                                 #
# --------------------------------------------------------------------------- #


class TestParseRdvProposalForm:
    """`_parse_rdv_proposal_form` converts the journalist's POST into
    a frozen `RDVProposalData`. All validation lives here, so each
    defensive branch deserves a pinned test.
    """

    def _call(self, app, form_data):
        view = AvisEnqueteWipView()
        with app.test_request_context(method="POST", data=form_data):
            return view._parse_rdv_proposal_form()

    def test_happy_path_parses_full_payload(self, app):
        data = self._call(
            app,
            {
                "rdv_type": "PHONE",
                "slot_datetime_1": "2030-01-15T10:00:00",
                "slot_datetime_2": "2030-01-16T11:30:00",
                "rdv_phone": "+33 1 23 45 67 89",
                "rdv_notes": "Appeler avant 18h.",
            },
        )
        assert isinstance(data, RDVProposalData)
        assert data.rdv_type is RDVType.PHONE
        # `datetime.fromisoformat` in the SUT returns *naive* dt
        # because the form lacks a timezone — pin the same shape.
        assert data.proposed_slots == [
            datetime(2030, 1, 15, 10, 0),  # noqa: DTZ001
            datetime(2030, 1, 16, 11, 30),  # noqa: DTZ001
        ]
        assert data.rdv_phone == "+33 1 23 45 67 89"
        assert data.rdv_notes == "Appeler avant 18h."
        # Untouched optional fields default to empty strings.
        assert data.rdv_video_link == ""
        assert data.rdv_address == ""

    def test_missing_rdv_type_raises(self, app):
        with pytest.raises(ValueError, match="Type de rendez-vous requis"):
            self._call(app, {})

    def test_unknown_rdv_type_raises(self, app):
        with pytest.raises(ValueError, match="Type de rendez-vous invalide"):
            self._call(app, {"rdv_type": "TELEPATHY"})

    def test_invalid_slot_isoformat_raises_with_slot_index(self, app):
        # The error message MUST identify which slot is malformed so
        # the journalist can fix the right field.
        with pytest.raises(ValueError, match="créneau 2"):
            self._call(
                app,
                {
                    "rdv_type": "VIDEO",
                    "slot_datetime_1": "2030-01-15T10:00:00",
                    "slot_datetime_2": "not-a-date",
                },
            )

    def test_empty_slot_strings_are_skipped(self, app):
        # The UI sends empty strings for unused slot rows; they must
        # not turn into spurious validation errors.
        data = self._call(
            app,
            {
                "rdv_type": "F2F",
                "slot_datetime_1": "",
                "slot_datetime_3": "2030-02-01T09:00:00",
                "slot_datetime_5": "",
            },
        )
        assert data.proposed_slots == [datetime(2030, 2, 1, 9, 0)]  # noqa: DTZ001

    def test_caps_at_five_slots(self, app):
        # The form only iterates 1..5; a sixth slot must be ignored
        # silently so a tampered form cannot smuggle extra slots.
        payload = {"rdv_type": "PHONE"}
        for i in range(1, 7):
            payload[f"slot_datetime_{i}"] = f"2030-03-0{i}T10:00:00"
        data = self._call(app, payload)
        assert len(data.proposed_slots) == 5
        assert data.proposed_slots[-1] == datetime(2030, 3, 5, 10, 0)  # noqa: DTZ001


class TestParseRdvAcceptanceForm:
    """`_parse_rdv_acceptance_form` parses the expert's POST. Note
    the `"decline"` sentinel: returning None signals refusal to the
    caller, which then routes to `refuse_rdv`.
    """

    def _call(self, app, form_data):
        view = AvisEnqueteWipView()
        with app.test_request_context(method="POST", data=form_data):
            return view._parse_rdv_acceptance_form()

    def test_happy_path_returns_dataclass(self, app):
        data = self._call(
            app,
            {
                "selected_slot": "2030-04-10T15:30:00",
                "expert_notes": "Préférence pour la visio.",
            },
        )
        assert isinstance(data, RDVAcceptanceData)
        # Naive datetime: form input has no timezone (see parser).
        assert data.selected_slot == datetime(2030, 4, 10, 15, 30)  # noqa: DTZ001
        assert data.expert_notes == "Préférence pour la visio."

    def test_decline_sentinel_returns_none(self, app):
        # The CBV interprets `None` as "expert declined" — losing
        # this branch would silently 500 instead of refusing.
        result = self._call(app, {"selected_slot": "decline"})
        assert result is None

    def test_missing_slot_raises(self, app):
        with pytest.raises(ValueError, match="Aucun créneau sélectionné"):
            self._call(app, {})

    def test_invalid_slot_isoformat_raises(self, app):
        with pytest.raises(ValueError, match="Format de créneau invalide"):
            self._call(app, {"selected_slot": "not-a-date"})

    def test_expert_notes_default_to_empty_string(self, app):
        data = self._call(app, {"selected_slot": "2030-05-01T09:00:00"})
        assert data is not None
        assert data.expert_notes == ""


# --------------------------------------------------------------------------- #
# Module-level helpers / constants                                            #
# --------------------------------------------------------------------------- #


class TestOpportunitiesUrlBuilder:
    """Passed as `opportunities_url_builder` to
    `PublicationNotificationService.notify_from_avis` and used to set
    the `url` field on the in-app notification + the link in the
    outgoing mail.
    """

    def test_returns_absolute_string_url(self, app):
        # The notif arg is unused (`_notif`) so any stand-in is fine.
        with app.test_request_context():
            url = _opportunities_url_builder(SimpleNamespace())
        assert isinstance(url, str)
        # Must be absolute so the email link is clickable from a mail
        # client outside of any HTTP request scope.
        assert url.startswith(("http://", "https://"))
        assert "opportunit" in url


class TestStepNavTemplates:
    """The #0151 step-nav bar must frame the rendered form on the
    "Voir" and "Modifier" steps. Pinning the template scaffolding
    prevents accidental loss of the navigation bar (which has
    regressed before).
    """

    @pytest.mark.parametrize("template", [_VOIR_TEMPLATE, _MODIFIER_TEMPLATE])
    def test_extends_shared_layout(self, template):
        assert '{% extends "wip/layout/_base.j2" %}' in template

    @pytest.mark.parametrize("template", [_VOIR_TEMPLATE, _MODIFIER_TEMPLATE])
    def test_imports_step_nav_macro(self, template):
        assert 'from "wip/avis_enquete/_step_nav.j2" import step_nav' in template

    def test_voir_template_brackets_form_with_step_nav(self):
        # `step_nav(avis, "voir")` must appear TWICE so the bar is
        # rendered at the top and the bottom of the form.
        assert _VOIR_TEMPLATE.count('step_nav(avis, "voir")') == 2
        # The form body and the gallery (extra_view_html, #0128) must
        # both be rendered safely between the two nav bars.
        assert "form_rendered|safe" in _VOIR_TEMPLATE
        assert "extra_view_html|safe" in _VOIR_TEMPLATE

    def test_modifier_template_brackets_form_with_step_nav(self):
        assert _MODIFIER_TEMPLATE.count('step_nav(avis, "modifier")') == 2
        assert "form_rendered|safe" in _MODIFIER_TEMPLATE
        # Modify step has NO extra gallery — keep it out, otherwise
        # we'd reintroduce the bug that #0128 fixed in view-only mode.
        assert "extra_view_html" not in _MODIFIER_TEMPLATE

    def test_templates_pass_model_under_avis_key_not_model(self):
        # If we expose the model as `model`, `@templated`'s enrich
        # context runs OpenGraph (url_for(obj)) which 500s for
        # AvisEnquete (no URL rule). Keep `avis` only.
        for tpl in (_VOIR_TEMPLATE, _MODIFIER_TEMPLATE):
            # `avis` must appear, bare `model` must NOT be the macro
            # argument used by step_nav.
            assert "step_nav(avis" in tpl
            assert "step_nav(model" not in tpl
