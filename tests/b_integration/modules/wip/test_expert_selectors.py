# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for expert selectors."""

from __future__ import annotations

from json import loads
from typing import TYPE_CHECKING

import pytest

from app.models.auth import KYCProfile, User
from app.modules.wip.services.newsroom.expert_selectors import (
    CompetencesGeneralesSelector,
    DepartementSelector,
    FilterOption,
    FonctionAssociationsSyndicatsSelector,
    FonctionOrganisationsPriveesSelector,
    FonctionPolitiquesAdministrativesSelector,
    FonctionSelector,
    LanguesSelector,
    MetierSelector,
    PaysSelector,
    SecteurSelector,
    TailleOrganisationSelector,
    TypeOrganisationSelector,
    VilleSelector,
)
from app.services.taxonomies import create_entry

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@pytest.fixture
def experts_with_profiles(db_session: Session) -> list[User]:
    """Create test experts with detailed profiles."""
    experts_data = [
        {
            "email": "expert1@test.com",
            "first_name": "Alice",
            "last_name": "Expert",
            "match_making": {
                "secteurs_activite": ["Tech", "Media"],
                "toutes_fonctions": ["Director", "Manager"],
                "competences": ["Python", "Data Analysis"],
                "type_organisation": ["Startup"],
                "taille_organisation": ["S1"],
                "langues": ["fr", "en"],
            },
            "info_professionnelle": {
                "pays_zip_ville": "FR",
                "pays_zip_ville_detail": ["FR 75000 Paris"],
                "secteurs_activite_medias_detail": ["Tech", "Media"],
                "type_orga_detail": ["Startup"],
                "taille_orga": ["S1"],
            },
        },
        {
            "email": "expert2@test.com",
            "first_name": "Bob",
            "last_name": "Expert",
            "match_making": {
                "secteurs_activite": ["Finance", "Tech"],
                "toutes_fonctions": ["Analyst"],
                "competences": ["Excel", "Finance"],
                "type_organisation": ["Corporate"],
                "taille_organisation": ["S3"],
                "langues": ["fr", "de"],
            },
            "info_professionnelle": {
                "pays_zip_ville": "FR",
                "pays_zip_ville_detail": ["FR 69000 Lyon"],
                "secteurs_activite_medias_detail": ["Finance", "Tech"],
                "type_orga_detail": ["Corporate"],
                "taille_orga": ["S3"],
            },
        },
        {
            "email": "expert3@test.com",
            "first_name": "Charlie",
            "last_name": "Expert",
            "match_making": {
                "secteurs_activite": ["Tech"],
                "toutes_fonctions": ["Developer"],
                "competences": ["Python", "JavaScript"],
                "type_organisation": ["Agency"],
                "taille_organisation": ["S2"],
                "langues": ["en", "es"],
            },
            "info_professionnelle": {
                "pays_zip_ville": "DE",
                "pays_zip_ville_detail": [],
                "secteurs_activite_medias_detail": ["Tech"],
                "type_orga_detail": ["Agency"],
                "taille_orga": ["S2"],
            },
        },
    ]

    users = []
    for data in experts_data:
        profile = KYCProfile(
            match_making=data["match_making"],
            info_professionnelle=data["info_professionnelle"],
        )

        user = User(
            email=data["email"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            active=True,
        )
        user.profile = profile
        db_session.add(user)
        users.append(user)

    db_session.flush()
    return users


class TestFilterOption:
    """Tests for FilterOption dataclass."""

    def test_filter_option_creation(self):
        """Test FilterOption can be created with required fields."""
        option = FilterOption(id="tech", label="Technology")

        assert option.id == "tech"
        assert option.label == "Technology"
        assert option.selected == ""

    def test_filter_option_with_selected(self):
        """Test FilterOption with selected status."""
        option = FilterOption(id="tech", label="Technology", selected="selected")

        assert option.selected == "selected"

    def test_filter_option_ordering(self):
        """Test FilterOption ordering by id."""
        option1 = FilterOption(id="a", label="Alpha")
        option2 = FilterOption(id="b", label="Beta")

        assert option1 < option2

    def test_filter_option_immutable(self):
        """Test FilterOption is immutable (frozen)."""
        option = FilterOption(id="tech", label="Technology")

        with pytest.raises(AttributeError):
            option.id = "other"  # type: ignore[misc]


class TestSecteurSelector:
    """Tests for SecteurSelector."""

    def test_get_values_returns_all_sectors(self, experts_with_profiles):
        """Test get_values returns all unique sectors."""
        state = {}
        selector = SecteurSelector(state, experts_with_profiles)
        values = selector.get_values()

        assert "Tech" in values
        assert "Media" in values
        assert "Finance" in values

    def test_filter_experts_by_sector(self, experts_with_profiles):
        """Test filtering experts by sector."""
        state = {}
        selector = SecteurSelector(state, experts_with_profiles)
        result = selector.filter_experts({"Finance"}, experts_with_profiles)

        assert len(result) == 1
        assert result[0].email == "expert2@test.com"

    def test_filter_experts_by_multiple_sectors(self, experts_with_profiles):
        """Test filtering experts by multiple sectors."""
        state = {}
        selector = SecteurSelector(state, experts_with_profiles)
        result = selector.filter_experts({"Tech", "Finance"}, experts_with_profiles)

        # All three have either Tech or Finance
        assert len(result) == 3

    def test_filter_with_empty_criteria_returns_all(self, experts_with_profiles):
        """Test filtering with empty criteria returns all experts."""
        state = {}
        selector = SecteurSelector(state, experts_with_profiles)
        result = selector.filter_experts(set(), experts_with_profiles)

        assert len(result) == len(experts_with_profiles)


class TestMetierSelector:
    """Tests for MetierSelector."""

    def test_selector_has_correct_id(self, experts_with_profiles):
        """Test selector has correct id."""
        state = {}
        selector = MetierSelector(state, experts_with_profiles)

        assert selector.id == "metier"
        assert selector.label == "Métier"


class TestFonctionSelector:
    """Tests for FonctionSelector."""

    def test_selector_has_correct_id(self, experts_with_profiles):
        """Test selector has correct id and label."""
        state = {}
        selector = FonctionSelector(state, experts_with_profiles)

        assert selector.id == "fonction"
        assert selector.label == "Toutes fonctions"

    def test_filter_with_no_criteria_returns_all(self, experts_with_profiles):
        """Test filtering with empty criteria returns all experts."""
        state = {}
        selector = FonctionSelector(state, experts_with_profiles)
        result = selector.filter_experts(set(), experts_with_profiles)

        assert len(result) == len(experts_with_profiles)


class TestCompetencesGeneralesSelector:
    """Tests for CompetencesGeneralesSelector."""

    def test_selector_has_correct_id(self, experts_with_profiles):
        """Test selector has correct id and label."""
        state = {}
        selector = CompetencesGeneralesSelector(state, experts_with_profiles)

        assert selector.id == "competences"
        assert selector.label == "Compétences générales"

    def test_filter_with_no_criteria_returns_all(self, experts_with_profiles):
        """Test filtering with empty criteria returns all experts."""
        state = {}
        selector = CompetencesGeneralesSelector(state, experts_with_profiles)
        result = selector.filter_experts(set(), experts_with_profiles)

        assert len(result) == len(experts_with_profiles)


class TestTypeOrganisationSelector:
    """Tests for TypeOrganisationSelector."""

    def test_get_values_returns_all_types(self, experts_with_profiles):
        """Test get_values returns all organization types."""
        state = {}
        selector = TypeOrganisationSelector(state, experts_with_profiles)
        values = selector.get_values()

        assert "Startup" in values
        assert "Corporate" in values
        assert "Agency" in values

    def test_filter_experts_by_org_type(self, experts_with_profiles):
        """Test filtering experts by organization type."""
        state = {}
        selector = TypeOrganisationSelector(state, experts_with_profiles)
        result = selector.filter_experts({"Startup"}, experts_with_profiles)

        assert len(result) == 1
        assert result[0].email == "expert1@test.com"


class TestTailleOrganisationSelector:
    """Tests for TailleOrganisationSelector."""

    def test_selector_has_correct_id(self, experts_with_profiles):
        """Test selector has correct id."""
        state = {}
        selector = TailleOrganisationSelector(state, experts_with_profiles)

        assert selector.id == "taille_organisation"


class TestLanguesSelector:
    """Tests for LanguesSelector."""

    def test_selector_has_correct_id(self, experts_with_profiles):
        """Test selector has correct id and label."""
        state = {}
        selector = LanguesSelector(state, experts_with_profiles)

        assert selector.id == "langues"
        assert selector.label == "Langues"

    def test_filter_with_no_criteria_returns_all(self, experts_with_profiles):
        """Test filtering with empty criteria returns all experts."""
        state = {}
        selector = LanguesSelector(state, experts_with_profiles)
        result = selector.filter_experts(set(), experts_with_profiles)

        assert len(result) == len(experts_with_profiles)


class TestPaysSelector:
    """Tests for PaysSelector."""

    def test_get_values_returns_all_countries(self, experts_with_profiles):
        """Test get_values returns all countries."""
        state = {}
        selector = PaysSelector(state, experts_with_profiles)
        values = selector.get_values()

        assert "FR" in values
        assert "DE" in values

    def test_filter_experts_by_country(self, experts_with_profiles):
        """Test filtering experts by country."""
        state = {}
        selector = PaysSelector(state, experts_with_profiles)
        result = selector.filter_experts({"FR"}, experts_with_profiles)

        assert len(result) == 2
        emails = [e.email for e in result]
        assert "expert1@test.com" in emails
        assert "expert2@test.com" in emails


class TestDepartementSelector:
    """Tests for DepartementSelector."""

    def test_get_values_empty_when_no_country_selected(self, experts_with_profiles):
        """Test get_values returns empty when no country is selected."""
        state = {}
        selector = DepartementSelector(state, experts_with_profiles)
        values = selector.get_values()

        assert values == set()

    def test_selector_has_correct_id(self, experts_with_profiles):
        """Test selector has correct id and label."""
        state = {}
        selector = DepartementSelector(state, experts_with_profiles)

        assert selector.id == "departement"
        assert selector.label == "Département"

    def test_filter_with_no_criteria_returns_all(self, experts_with_profiles):
        """Test filtering with empty criteria returns all experts."""
        state = {}
        selector = DepartementSelector(state, experts_with_profiles)
        result = selector.filter_experts(set(), experts_with_profiles)

        assert len(result) == len(experts_with_profiles)


class TestVilleSelector:
    """Tests for VilleSelector."""

    def test_get_values_empty_when_no_department_selected(self, experts_with_profiles):
        """Test get_values returns empty when no department is selected."""
        state = {}
        selector = VilleSelector(state, experts_with_profiles)
        values = selector.get_values()

        assert values == set()

    def test_selector_has_correct_id(self, experts_with_profiles):
        """Test selector has correct id and label."""
        state = {}
        selector = VilleSelector(state, experts_with_profiles)

        assert selector.id == "ville"
        assert selector.label == "Ville"

    def test_filter_with_no_criteria_returns_all(self, experts_with_profiles):
        """Test filtering with empty criteria returns all experts."""
        state = {}
        selector = VilleSelector(state, experts_with_profiles)
        result = selector.filter_experts(set(), experts_with_profiles)

        assert len(result) == len(experts_with_profiles)


class TestBaseSelectorOptions:
    """Tests for BaseSelector.options property."""

    def test_options_returns_list_of_filter_options(self, experts_with_profiles):
        """Test options returns list of FilterOption."""
        state = {}
        selector = SecteurSelector(state, experts_with_profiles)
        options = selector.options

        assert isinstance(options, list)
        assert all(isinstance(opt, FilterOption) for opt in options)

    def test_options_marks_selected_values(self, experts_with_profiles):
        """Test options marks selected values."""
        state = {"secteur": ["Tech"]}
        selector = SecteurSelector(state, experts_with_profiles)
        options = selector.options

        tech_option = next((o for o in options if o.id == "Tech"), None)
        assert tech_option is not None
        assert tech_option.selected == "selected"

    def test_options_sorted_alphabetically(self, experts_with_profiles):
        """Test options are sorted alphabetically ignoring diacritics."""
        state = {}
        selector = SecteurSelector(state, experts_with_profiles)
        options = selector.options

        # Check options are sorted
        labels = [o.label for o in options]
        assert labels == sorted(labels)


class TestOntologyBackedOptions:
    """Phase 1 of bug #0150 (Annie / ciblage taxonomies tronquées).

    Selectors with a `taxonomy_name` surface the **full** KYC ontology
    in their option list, not just values present in the candidate
    expert pool. Each option carries a `(N)` count of matching experts
    so the user knows up-front whether selecting a criterion will
    zero out the result set.
    """

    def test_secteur_options_include_zero_match_taxonomy_entries(
        self, experts_with_profiles, db_session
    ):
        """A taxonomy entry that no expert holds still appears in the
        dropdown, with `(0)` so the user knows it's empty.

        Taxonomy entries are addressed by their `name` (what's stored
        on KYC profiles), so we assert against the name we injected.
        """
        create_entry(
            taxonomy_name="secteur_detaille",
            name="Phantom sector",
            category="Other",
            value="phantom_sector_xyz",
        )
        db_session.flush()

        state = {}
        selector = SecteurSelector(state, experts_with_profiles)
        option_ids = {o.id for o in selector.options}
        assert "Phantom sector" in option_ids, (
            "Full taxonomy must surface in dropdown even when 0 experts match"
        )
        phantom = next(o for o in selector.options if o.id == "Phantom sector")
        assert phantom.label.endswith("(0)"), (
            f"Zero-match option must carry `(0)` badge, got {phantom.label!r}"
        )

    def test_option_label_carries_count_badge(self, experts_with_profiles):
        """Every option's label ends with ` (N)` where N is the count
        of experts in the pool matching that value."""
        state = {}
        selector = SecteurSelector(state, experts_with_profiles)
        # Fixture has 3 experts: Alice/Bob/Charlie all hold "Tech".
        tech = next((o for o in selector.options if o.id == "Tech"), None)
        assert tech is not None
        assert tech.label == "Tech (3)", (
            f"Expected `Tech (3)`, got {tech.label!r}. Counts feed the user's "
            "decision to keep a criterion or drop it before the result set "
            "shrinks to 0."
        )

    def test_count_badge_zero_for_pool_misses(self, experts_with_profiles):
        """An option held by zero experts shows `(0)` — not omitted,
        not blank."""
        state = {}
        selector = SecteurSelector(state, experts_with_profiles)
        non_match = next(
            (o for o in selector.options if o.id not in {"Tech", "Media", "Finance"}),
            None,
        )
        if non_match is None:
            pytest.skip("Test taxonomy doesn't expose a non-matching entry")
        assert non_match.label.endswith("(0)"), (
            f"Non-matching taxonomy option must carry `(0)`, got {non_match.label!r}"
        )

    def test_no_hard_cap_on_option_count(self, experts_with_profiles, db_session):
        """Bug #0150 root: `MAX_OPTIONS = 100` truncated the dropdown
        — the user couldn't reach taxonomies beyond the first 100
        entries. The cap is gone; we surface every taxonomy entry.
        """
        # Inject 150 phantom entries to prove the cap is gone.
        for i in range(150):
            create_entry(
                taxonomy_name="secteur_detaille",
                name=f"Phantom {i:03d}",
                category="Bench",
                value=f"phantom_{i:03d}",
            )
        db_session.flush()

        state = {}
        selector = SecteurSelector(state, experts_with_profiles)
        assert len(selector.options) > 100, (
            "Dropdown must not cap at 100 options — that was the "
            "« tronqué » symptom Annie reported."
        )


class TestBaseSelectorValues:
    """Tests for BaseSelector.values initialization."""

    def test_values_initialized_from_state(self, experts_with_profiles):
        """Test values are initialized from state."""
        state = {"secteur": ["Tech", "Media"]}
        selector = SecteurSelector(state, experts_with_profiles)

        assert selector.values == {"Tech", "Media"}

    def test_values_empty_when_no_state(self, experts_with_profiles):
        """Test values are empty when no state."""
        state = {}
        selector = SecteurSelector(state, experts_with_profiles)

        assert selector.values == set()

    def test_values_handles_string_state(self, experts_with_profiles):
        """Test values handle string state (single value)."""
        state = {"secteur": "Tech"}
        selector = SecteurSelector(state, experts_with_profiles)

        assert selector.values == {"Tech"}


class TestDualSelector:
    """Phase 3 of bug #0150 (Annie's ciblage request): 7 fields render
    as a parent → child cascade, reusing KYC's dual_select_multi
    widget shape (so we inherit the #0119 fix that made it actually
    work)."""

    def test_dual_selectors_advertise_themselves(self, experts_with_profiles):
        """Each of the 7 cascading selectors sets `is_dual = True`
        so the template can route it to the cascade partial instead
        of the flat dropdown macro."""
        state: dict = {}
        duals = [
            SecteurSelector(state, experts_with_profiles),
            TypeOrganisationSelector(state, experts_with_profiles),
            FonctionPolitiquesAdministrativesSelector(state, experts_with_profiles),
            FonctionOrganisationsPriveesSelector(state, experts_with_profiles),
            FonctionAssociationsSyndicatsSelector(state, experts_with_profiles),
            MetierSelector(state, experts_with_profiles),
            CompetencesGeneralesSelector(state, experts_with_profiles),
        ]
        for s in duals:
            assert s.is_dual is True, (
                f"{type(s).__name__} should render as a dual cascade"
            )
            assert s.parent_id, f"{type(s).__name__} missing parent_id"
            assert s.parent_id != s.id, (
                f"{type(s).__name__} parent_id must differ from id "
                "(they are independent form fields)"
            )
            assert s.taxonomy_name, f"{type(s).__name__} missing taxonomy_name"

    def test_get_data_returns_list_of_parent_selection(self, experts_with_profiles):
        """`get_data()` returns the list of selected parents. The
        template serializes via `| tojson` so we don't `repr()` here
        — repr-ing would conflict with Jinja autoescape on `.j2`
        includes (every `'` would be HTML-encoded into the inline JS)."""
        state = {"secteur_parent": ["Agriculture", "Tech"]}
        selector = SecteurSelector(state, experts_with_profiles)
        result = selector.get_data()
        assert isinstance(result, list)
        assert set(result) == {"Agriculture", "Tech"}

    def test_get_data2_returns_list_of_child_selection(self, experts_with_profiles):
        """`get_data2()` returns the (sorted) list of selected child values."""
        state = {"secteur": ["Tech", "Media"]}
        selector = SecteurSelector(state, experts_with_profiles)
        result = selector.get_data2()
        assert isinstance(result, list)
        assert set(result) == {"Tech", "Media"}

    def test_get_data_empty_when_no_parent_selected(self, experts_with_profiles):
        """An empty cascade returns `[]` — never `None`."""
        state = {}
        selector = SecteurSelector(state, experts_with_profiles)
        assert selector.get_data() == []
        assert selector.get_data2() == []

    def test_dual_choices_for_js_has_field1_and_field2(
        self, experts_with_profiles, db_session
    ):
        """`get_dual_tom_choices_for_js()` returns a dict with `field1`
        (parents) and `field2` (qualified `Parent / Child` items) —
        the shape `dual_select_multi.j2` consumes.

        Production taxonomy entries for dual fields use qualified
        `"Parent / Child"` values (the bootstrap formats them that
        way); the test seeds the same shape so the JS-side parent
        derivation (`value.split(' / ')[0]`) works end-to-end.
        """
        create_entry(
            taxonomy_name="secteur_detaille",
            name="Agriculture / Viticulture",
            category="Agriculture",
            value="Agriculture / Viticulture",
        )
        create_entry(
            taxonomy_name="secteur_detaille",
            name="Agriculture / Élevage",
            category="Agriculture",
            value="Agriculture / Élevage",
        )
        db_session.flush()

        state: dict = {}
        selector = SecteurSelector(state, experts_with_profiles)
        choices = selector.get_dual_tom_choices_for_js()
        assert "field1" in choices
        assert "field2" in choices
        # field1 = parent categories
        parent_labels = {row["label"] for row in choices["field1"]}
        assert "Agriculture" in parent_labels
        # field2 = qualified Parent / Child entries
        child_labels = {row["label"] for row in choices["field2"]}
        assert any(label.startswith("Agriculture / ") for label in child_labels), (
            f"Expected `Agriculture / X` entries, got {child_labels}"
        )

    def test_filter_still_uses_child_values(self, experts_with_profiles):
        """The cascade upgrade is UI-only — the filter pipeline still
        compares against the expert's detail-list values exactly like
        the single-level selector did."""
        state = {}
        selector = SecteurSelector(state, experts_with_profiles)
        # Fixture: Bob/Charlie don't hold Finance — Bob does.
        result = selector.filter_experts({"Finance"}, experts_with_profiles)
        assert len(result) == 1
        assert result[0].email == "expert2@test.com"

    def test_render_payload_round_trips_through_tojson(
        self, experts_with_profiles, db_session, app
    ):
        r"""Regression for the « rendering horror »: the cascade payload
        must survive Jinja's autoescape on .j2 includes.

        Symptom history:
        1. The first version embedded the payload inline via
           `x-data="{ all_options: {{ ... | tojson }} }"`. tojson
           outputs literal `"` (JSON's own string delimiter), which
           terminated the double-quoted HTML attribute prematurely.
           Tom-Select never initialized.
        2. Switched to a `data-options='...'` (single-quoted) attribute
           because tojson escapes `'` to `'` — JSON's `"` is safe
           inside `'...'`.

        This test pins the contract: a single-quoted HTML attribute
        carrying `| tojson` output must round-trip when read back via
        `dataset.X`. If it ever stops, the cascade degrades to raw
        `<select>` again.
        """
        create_entry(
            taxonomy_name="secteur_detaille",
            name="L'industrie <auto>",
            category="Mobilités",
            value="Mobilités / L'industrie <auto>",
        )
        db_session.flush()

        state: dict = {}
        selector = SecteurSelector(state, experts_with_profiles)
        choices = selector.get_dual_tom_choices_for_js()

        # Embedded in a single-quoted HTML attribute (the shape
        # `_dual_selector.j2` actually emits). Extract via a naive
        # parse and reparse the JSON — proves nothing inside the
        # tojson output broke the `'` delimiter.
        with app.app_context():
            t_attr = app.jinja_env.from_string(
                "<div data-options='{{ x | tojson }}'></div>"
            )
            rendered = t_attr.render(x=choices)
        assert rendered.count("'") == 2, (
            "tojson output broke the single-quoted attribute "
            f"delimiter (extra `'` leaked through): {rendered!r}. "
            "If this fails, the data-options attribute will be "
            "truncated and JSON.parse(container.dataset.options) will "
            "throw — Tom-Select stays on the original empty <select>."
        )
        inner = rendered.split("'")[1]
        assert loads(inner) == choices

        # And the raw tojson output is parseable JSON too.
        with app.app_context():
            t = app.jinja_env.from_string("{{ x | tojson }}")
            json_payload = t.render(x=choices)
            roundtrip = loads(json_payload)
        assert roundtrip == choices, (
            "tojson must round-trip without losing data — if this fails, "
            "the inline JS in _dual_selector.j2 will not parse the "
            "taxonomy options and the cascade UI will degrade to raw "
            "<select> elements."
        )
