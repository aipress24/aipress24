# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the pure helpers extracted from `wip/crud/cbvs/_base.py`.

The CBV base class itself (`BaseWipView`) is request-handler scaffolding:
its public methods read from `flask.g`, hit the DB through SQLAlchemy
sessions and resolve URLs through `flask.url_for`. None of that is
unit-testable in isolation — it belongs to the integration suite.

What *is* unit-testable is the pure logic the shell delegates to:

- `get_name(obj)` — null-safe accessor used by table renderers (no IO).
- `_format_publisher_label(name)` — single source of truth for the
  « Publié pour le compte de … » header. Pins the exact string format
  so regressions in any of the three publisher branches surface as a
  format diff rather than a quiet HTML mismatch.
- `_resolve_publisher_text(...)` — bug #0135. The branching that picks
  the right organisation name to show in the form header. Has three
  exhaustive branches (model.publisher / managed BW / user own org)
  with `bw_name` fallbacks; all of them are exercised here with
  duck-typed stand-in classes (no Flask, no DB, no mocks).
- `_build_index_breadcrumbs(...)` / `_build_phase_breadcrumbs(...)` —
  the trail composition. The shell resolves URLs via `url_for`; the
  pure helper just assembles the right `BreadCrumb` sequence given
  those URLs.
- `_sort_org_choices(orgs, pinned_org=...)` — the (id, name) list the
  media picker feeds to the WTForms select. Sort order and the pinned
  insertion at index 0 are part of the contract.
- `LIST_TEMPLATE` / `UPDATE_TEMPLATE` / `VIEW_TEMPLATE` — module-level
  Jinja2 strings used by `@templated`. Pinning the extends/blocks
  catches accidental template scaffolding loss.
- `BaseWipView` class-level config — abstract base, but `route_prefix`
  is pinned and the ABC contract guards against accidental instantiation.

Only plain duck-typed stand-in classes (`_Org`, `_Model`) are used as
collaborators here, satisfying the attribute contract the SUT reads
from without any test-double library.
"""

from __future__ import annotations

import abc

import pytest

from app.flask.lib.breadcrumbs import BreadCrumb
from app.modules.wip.crud.cbvs._base import (
    LIST_TEMPLATE,
    UPDATE_TEMPLATE,
    VIEW_TEMPLATE,
    BaseWipView,
    _build_index_breadcrumbs,
    _build_phase_breadcrumbs,
    _format_publisher_label,
    _resolve_publisher_text,
    _sort_org_choices,
    get_name,
)

# --------------------------------------------------------------------- #
# Stand-in duck types                                                   #
# --------------------------------------------------------------------- #


class _Org:
    """Minimal stand-in for `app.models.organisation.Organisation`.

    The SUT only reads `id`, `name` and `bw_name` from an org instance.
    Anything beyond that would couple the unit test to the SQLAlchemy
    model definition unnecessarily.
    """

    def __init__(self, *, id, name: str, bw_name: str = "") -> None:
        self.id = id
        self.name = name
        self.bw_name = bw_name


class _Model:
    """Stand-in for a CBV-managed model with an optional `.publisher`."""

    def __init__(self, *, publisher=None, title: str = "Untitled") -> None:
        self.publisher = publisher
        self.title = title


# --------------------------------------------------------------------- #
# get_name                                                              #
# --------------------------------------------------------------------- #


class TestGetName:
    """`get_name` is the null-safe accessor used by table column
    renderers when the cell value may be a related object or None.
    """

    def test_returns_attribute_when_object_present(self):
        org = _Org(id=1, name="Le Monde")
        assert get_name(org) == "Le Monde"

    @pytest.mark.parametrize("falsy", [None, 0, "", False])
    def test_returns_empty_string_for_falsy(self, falsy):
        # The template renders the result raw: returning "" guarantees
        # the cell stays empty rather than printing "None" or "False".
        assert get_name(falsy) == ""


# --------------------------------------------------------------------- #
# _format_publisher_label                                               #
# --------------------------------------------------------------------- #


class TestFormatPublisherLabel:
    """Single source of truth for the « Publié pour le compte de X »
    header. Pin the exact format string so any of the three publisher
    branches surfaces as a format diff, not a quiet HTML mismatch.
    """

    def test_wraps_name_with_quotes_and_prefix(self):
        assert (
            _format_publisher_label("Le Monde") == 'Publié pour le compte de "Le Monde"'
        )

    def test_passes_name_through_unmodified(self):
        # Quotes inside the name are kept as-is — escaping is the
        # template's responsibility, not the helper's.
        assert (
            _format_publisher_label('AFP "Special"')
            == 'Publié pour le compte de "AFP "Special""'
        )

    def test_handles_empty_string(self):
        # Defensive: caller should guard against empty names, but the
        # helper itself stays predictable rather than raising.
        assert _format_publisher_label("") == 'Publié pour le compte de ""'


# --------------------------------------------------------------------- #
# _resolve_publisher_text — bug #0135                                   #
# --------------------------------------------------------------------- #


class TestResolvePublisherText:
    """The three publisher branches from bug #0135.

    Priority order (highest to lowest):
      1. `model.publisher` (the actual published-for client) — wins
         even if the editing user is managing another BW.
      2. `user.is_managing_another_bw` + selected BW — the agency
         member is currently acting for another client.
      3. `user.organisation` — fallback to the editing user's own org
         when creating a new model.

    Each branch prefers `bw_name` over `name` when the org carries
    both (the BW header is the user-visible publishing name).
    """

    def test_model_publisher_wins_with_bw_name(self):
        org = _Org(id=1, name="Group SA", bw_name="Le Quotidien")
        model = _Model(publisher=org)
        result = _resolve_publisher_text(
            model,
            user_is_managing_another_bw=True,
            selected_bw_name="Selected BW",
            user_org=_Org(id=99, name="Own"),
        )
        # Even though both fallbacks are present, the model's publisher
        # wins — and uses bw_name in preference to the legal name.
        assert result == 'Publié pour le compte de "Le Quotidien"'

    def test_model_publisher_falls_back_to_name_when_no_bw_name(self):
        org = _Org(id=2, name="L'Express", bw_name="")
        model = _Model(publisher=org)
        result = _resolve_publisher_text(
            model,
            user_is_managing_another_bw=False,
            selected_bw_name=None,
            user_org=None,
        )
        assert result == 'Publié pour le compte de "L\'Express"'

    def test_managed_bw_branch_when_no_model_publisher(self):
        # User is editing a model that has no publisher (typically a
        # draft) and is currently managing another BW. The selected
        # BW name drives the header.
        model = _Model(publisher=None)
        result = _resolve_publisher_text(
            model,
            user_is_managing_another_bw=True,
            selected_bw_name="Mediapart",
            user_org=_Org(id=99, name="Own", bw_name="Should be ignored"),
        )
        assert result == 'Publié pour le compte de "Mediapart"'

    def test_managed_bw_with_no_selected_bw_returns_empty(self):
        # Defensive: `is_managing_another_bw=True` but no BW is
        # currently selected (race / stale session). The helper must
        # NOT fall through to the user's own org — that's a different
        # branch with a different meaning.
        result = _resolve_publisher_text(
            None,
            user_is_managing_another_bw=True,
            selected_bw_name=None,
            user_org=_Org(id=99, name="Own"),
        )
        assert result == ""

    def test_user_org_branch_when_creating_new_model(self):
        # No model_publisher, not managing another BW: fall back to
        # the editing user's own organisation. bw_name preferred.
        result = _resolve_publisher_text(
            None,
            user_is_managing_another_bw=False,
            selected_bw_name=None,
            user_org=_Org(id=7, name="ACME SAS", bw_name="ACME News"),
        )
        assert result == 'Publié pour le compte de "ACME News"'

    def test_user_org_branch_falls_back_to_name(self):
        result = _resolve_publisher_text(
            None,
            user_is_managing_another_bw=False,
            selected_bw_name=None,
            user_org=_Org(id=7, name="ACME SAS", bw_name=""),
        )
        assert result == 'Publié pour le compte de "ACME SAS"'

    def test_no_branches_match_returns_empty_string(self):
        # A logged-in user with no model, not managing anything, and
        # no organisation must not produce a malformed header. Empty
        # string is the established contract.
        result = _resolve_publisher_text(
            None,
            user_is_managing_another_bw=False,
            selected_bw_name=None,
            user_org=None,
        )
        assert result == ""

    def test_model_without_publisher_attribute_uses_fallback(self):
        # Some models (e.g. early drafts) carry a `publisher` attribute
        # set to None. The branch must skip them as if absent.
        model = _Model(publisher=None)
        result = _resolve_publisher_text(
            model,
            user_is_managing_another_bw=False,
            selected_bw_name=None,
            user_org=_Org(id=1, name="Fallback Org"),
        )
        assert result == 'Publié pour le compte de "Fallback Org"'


# --------------------------------------------------------------------- #
# _build_index_breadcrumbs                                              #
# --------------------------------------------------------------------- #


class TestBuildIndexBreadcrumbs:
    """The index/new/edit breadcrumb trail. The shell resolves the URLs
    via Flask's `url_for`; the pure helper composes the right sequence.
    """

    def test_minimal_trail_has_work_and_list(self):
        crumbs = _build_index_breadcrumbs(
            work_url="/wip/",
            label_list="Articles",
            index_url="/wip/articles/",
        )
        assert crumbs == [
            BreadCrumb(label="Work", url="/wip/"),
            BreadCrumb(label="Articles", url="/wip/articles/"),
        ]

    def test_new_label_appended_with_empty_url(self):
        # The trailing "new" crumb has no URL — it's the current page.
        crumbs = _build_index_breadcrumbs(
            work_url="/wip/",
            label_list="Articles",
            index_url="/wip/articles/",
            new_label="Créer un article",
        )
        assert crumbs[-1] == BreadCrumb(label="Créer un article", url="")

    def test_extra_label_appended_with_empty_url(self):
        crumbs = _build_index_breadcrumbs(
            work_url="/wip/",
            label_list="Articles",
            index_url="/wip/articles/",
            extra_label='Modifier "Hello"',
        )
        assert crumbs[-1] == BreadCrumb(label='Modifier "Hello"', url="")

    def test_new_and_extra_both_present_keep_relative_order(self):
        # `new` lands before `extra` so the trail reads naturally.
        crumbs = _build_index_breadcrumbs(
            work_url="/wip/",
            label_list="Articles",
            index_url="/wip/articles/",
            new_label="Créer",
            extra_label="Brouillon",
        )
        assert [c.label for c in crumbs] == [
            "Work",
            "Articles",
            "Créer",
            "Brouillon",
        ]

    @pytest.mark.parametrize("falsy", ["", None])
    def test_empty_new_label_is_skipped(self, falsy):
        crumbs = _build_index_breadcrumbs(
            work_url="/wip/",
            label_list="Articles",
            index_url="/wip/articles/",
            new_label=falsy,
        )
        # Just Work + Articles, no trailing crumb.
        assert len(crumbs) == 2

    def test_empty_extra_label_is_skipped(self):
        crumbs = _build_index_breadcrumbs(
            work_url="/wip/",
            label_list="Articles",
            index_url="/wip/articles/",
            extra_label="",
        )
        assert len(crumbs) == 2


# --------------------------------------------------------------------- #
# _build_phase_breadcrumbs                                              #
# --------------------------------------------------------------------- #


class TestBuildPhaseBreadcrumbs:
    """Bugs #0070, #0085: sub-page trail with a clickable detail crumb
    so the user can jump back to the model's detail page without going
    all the way up to the Work dashboard.
    """

    def test_full_four_crumb_trail(self):
        crumbs = _build_phase_breadcrumbs(
            work_url="/wip/",
            label_list="Avis d'enquête",
            index_url="/wip/avis-enquete/",
            model_title="Mon avis",
            model_url="/wip/avis-enquete/42",
            phase="Ciblage",
        )
        assert crumbs == [
            BreadCrumb(label="Work", url="/wip/"),
            BreadCrumb(label="Avis d'enquête", url="/wip/avis-enquete/"),
            BreadCrumb(label="Mon avis", url="/wip/avis-enquete/42"),
            BreadCrumb(label="Ciblage", url=""),
        ]

    def test_model_title_crumb_is_clickable(self):
        # Regression guard for #0070: this crumb MUST carry the detail
        # URL so the user can click back. Empty url -> regression.
        crumbs = _build_phase_breadcrumbs(
            work_url="/wip/",
            label_list="Articles",
            index_url="/wip/articles/",
            model_title="Hello",
            model_url="/wip/articles/7",
            phase="Images",
        )
        title_crumb = crumbs[2]
        assert title_crumb.label == "Hello"
        assert title_crumb.url == "/wip/articles/7"

    def test_phase_crumb_is_terminal_no_url(self):
        # The current page never has a URL (no self-link).
        crumbs = _build_phase_breadcrumbs(
            work_url="/wip/",
            label_list="L",
            index_url="/i",
            model_title="T",
            model_url="/i/1",
            phase="Images",
        )
        assert crumbs[-1].url == ""


# --------------------------------------------------------------------- #
# _sort_org_choices                                                     #
# --------------------------------------------------------------------- #


class TestSortOrgChoices:
    """The media picker contract: alphabetic by display name, with the
    editing user's own org pinned to index 0 (under its bw_name label).
    """

    def test_sorts_by_name_alphabetically(self):
        orgs = [
            _Org(id=3, name="Zenith"),
            _Org(id=1, name="Alpha"),
            _Org(id=2, name="Midas"),
        ]
        result = _sort_org_choices(orgs)
        # IDs are stringified — WTForms select coercer is `str`.
        assert result == [("1", "Alpha"), ("2", "Midas"), ("3", "Zenith")]

    def test_ids_are_stringified(self):
        # The form coercer is str, so the choice values must already be
        # strings — passing ints would break WTForms matching.
        orgs = [_Org(id=42, name="X")]
        assert _sort_org_choices(orgs) == [("42", "X")]

    def test_pinned_org_is_inserted_first_with_bw_name_label(self):
        # The pinned (editing user's) org wears its `bw_name`, not its
        # legal `name` — that's the user-visible publishing identity.
        pinned = _Org(id=99, name="Group SA", bw_name="Le Quotidien")
        others = [_Org(id=1, name="Alpha"), _Org(id=2, name="Beta")]
        result = _sort_org_choices(others, pinned_org=pinned)
        assert result[0] == ("99", "Le Quotidien")
        # The remaining choices keep their sorted order.
        assert result[1:] == [("1", "Alpha"), ("2", "Beta")]

    def test_no_pinned_org_returns_only_sorted_list(self):
        orgs = [_Org(id=1, name="Alpha")]
        assert _sort_org_choices(orgs, pinned_org=None) == [("1", "Alpha")]

    def test_empty_input_returns_empty_list(self):
        assert _sort_org_choices([]) == []

    def test_empty_input_with_pinned_returns_only_pinned(self):
        # Defensive: even if the SQL query returns no other media orgs,
        # the user's own org must still appear at the top.
        pinned = _Org(id=1, name="Solo", bw_name="Solo BW")
        assert _sort_org_choices([], pinned_org=pinned) == [("1", "Solo BW")]


# --------------------------------------------------------------------- #
# Module-level Jinja2 templates                                         #
# --------------------------------------------------------------------- #


class TestSharedTemplates:
    """The three shared templates feed `@templated` for the index,
    update and view pages. Pin the scaffolding so accidental loss of
    `{% extends %}` or the body block surfaces as a test failure rather
    than a runtime template error.
    """

    @pytest.mark.parametrize(
        "template",
        [LIST_TEMPLATE, UPDATE_TEMPLATE, VIEW_TEMPLATE],
    )
    def test_extends_shared_layout(self, template):
        assert '{% extends "wip/layout/_base.j2" %}' in template

    @pytest.mark.parametrize(
        "template",
        [LIST_TEMPLATE, UPDATE_TEMPLATE, VIEW_TEMPLATE],
    )
    def test_defines_body_content_block(self, template):
        # `wip/layout/_base.j2` puts the page body inside this block;
        # losing the {% block body_content %} silently empties the page.
        assert "{% block body_content %}" in template
        assert "{% endblock %}" in template

    def test_list_template_renders_table(self):
        assert "table.render()" in LIST_TEMPLATE

    def test_update_template_renders_form(self):
        # `form_rendered` is piped through `|safe` because FormRenderer
        # already returns escaped HTML.
        assert "form_rendered|safe" in UPDATE_TEMPLATE

    def test_view_template_renders_form_and_extra_html(self):
        # Bug #0128: view mode adds a gallery (or other read-only HTML)
        # *below* the form — both pieces must be in the template.
        assert "form_rendered|safe" in VIEW_TEMPLATE
        assert "extra_view_html|safe" in VIEW_TEMPLATE


# --------------------------------------------------------------------- #
# BaseWipView class-level configuration                                 #
# --------------------------------------------------------------------- #


class TestBaseWipViewConfig:
    """`BaseWipView` is an ABC; subclasses fill in the model/repo/form
    wiring. Pin the few attributes that are inherited verbatim by every
    subclass so renaming one surfaces as a deliberate decision.
    """

    def test_route_prefix_is_wip(self):
        # All concrete WIP views inherit `/wip/` — this is the only
        # URL fragment defined at the abstract layer.
        assert BaseWipView.route_prefix == "/wip/"

    def test_is_an_abc(self):
        # Catches accidental removal of `abc.ABC` from the bases.
        assert issubclass(BaseWipView, abc.ABC)

    def test_post_update_model_hook_default_is_noop(self):
        # Subclasses override `_post_update_model` to add side effects
        # (notifications, sync calls). The default must NOT raise so
        # a subclass that doesn't override stays functional.
        class _Concrete(BaseWipView):
            pass

        instance = _Concrete.__new__(_Concrete)
        # No model state to mutate; the contract is "no exception".
        assert instance._post_update_model(object()) is None

    def test_extra_view_html_hook_default_is_empty_string(self):
        # `_extra_view_html` is the override seam for view-only HTML
        # below the form. Default must be "" so the template doesn't
        # render the literal "None".
        class _Concrete(BaseWipView):
            pass

        instance = _Concrete.__new__(_Concrete)
        assert instance._extra_view_html(object(), "view") == ""
        assert instance._extra_view_html(None, "edit") == ""
