# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Pin contracts of the WIP CRUD CBV table base classes.

This file complements ``test_table.py`` (which covers request-bound
pagination math and the ``app`` fixture flow) by pinning the things
that should be true *without* an application/request context:

* the ``get_name`` module-level helper used inside table renderers,
* the ``make_datasource`` factory wiring,
* the structural contract of ``BaseTable.get_columns`` (order, labels,
  CSS classes, sentinel ``$actions``),
* the structural contract of ``BaseTable.get_actions`` (label order,
  underlying ``url_for`` action argument),
* the ``_make_datasource`` subclass hook documented for bug 0132,
* the class hierarchy (``Table`` / ``DataSource`` inheritance).

The intent is purely structural: we exercise *pure* helpers / class
attributes and avoid touching the DB-bound code paths (``_base_query``,
``get_items``, ``get_count``) which are integration concerns.
"""

from __future__ import annotations

import pytest
from sqlalchemy import Column, DateTime

from app.modules.wip.components.table.table import DataSource, Table
from app.modules.wip.crud.cbvs._table import (
    BaseDataSource,
    BaseTable,
    get_name,
    make_datasource,
)


class _FakeModel:
    """Tiny stand-in to exercise ``get_order_by`` without importing a
    full SQLAlchemy model — we only need a ``created_at`` column that
    supports ``.desc()``."""

    created_at = Column("created_at", DateTime)


class _NamedStub:
    """Duck-typed stand-in for any object exposing ``.name``."""

    def __init__(self, name: str) -> None:
        self.name = name


class _ItemStub:
    """Stand-in for a row item passed to ``get_actions``/``get_media_name``."""

    def __init__(self, *, id: int = 1, media: object | None = None) -> None:
        self.id = id
        # Only set ``media`` if explicitly given so we can test the
        # ``getattr(obj, "media", None)`` defensive branch.
        if media is not None:
            self.media = media


class TestGetName:
    """``get_name`` is the tiny pure helper used to render foreign-key
    fields safely when the related object may be missing."""

    def test_returns_name_attribute_when_present(self):
        # WHY: happy path — pin that we read ``.name`` (not ``.title``,
        # ``.label``, ``str()``, etc.). Subclasses depend on this name.
        assert get_name(_NamedStub("Le Monde")) == "Le Monde"

    @pytest.mark.parametrize("falsy", [None, 0, "", False, []])
    def test_returns_empty_string_for_any_falsy_obj(self, falsy):
        # WHY: defensive branch — the function is meant to swallow
        # ``None`` foreign keys but its check is ``if obj``, so *any*
        # falsy value short-circuits to ``""``. Pin this so a future
        # refactor to ``if obj is None`` is a deliberate decision.
        assert get_name(falsy) == ""

    def test_returns_empty_string_preserves_type(self):
        # WHY: callers concatenate the result into Jinja templates; an
        # accidental ``None`` would render as the literal string
        # ``"None"``. Always return ``str``.
        result = get_name(None)
        assert isinstance(result, str)


class TestMakeDatasource:
    """The free-standing factory used by ``BaseTable.__init__``."""

    def test_returns_base_datasource_instance(self, app):
        # WHY: pins the factory return type — subclasses that override
        # ``_make_datasource`` must produce *something* compatible.
        with app.test_request_context():
            ds = make_datasource(model_class=object, q="hello")
        assert isinstance(ds, BaseDataSource)

    def test_propagates_query_and_model(self, app):
        # WHY: pin the parameter wiring; a typo swap would silently
        # break full-text search across all WIP listings.
        with app.test_request_context():
            ds = make_datasource(model_class=dict, q="needle")
        assert ds.q == "needle"
        assert ds.model_class is dict


class TestBaseDataSourceContract:
    """Pin the class-level contract of ``BaseDataSource`` — no DB."""

    def test_is_concrete_datasource_subclass(self):
        # WHY: the abstract ``DataSource`` declares ``get_items`` and
        # ``get_count`` as ``@abstractmethod``. Pin that BaseDataSource
        # implements both so it can be instantiated.
        assert issubclass(BaseDataSource, DataSource)
        # Both abstract methods must be implemented on the subclass.
        for name in ("get_items", "get_count"):
            assert getattr(BaseDataSource, name) is not getattr(DataSource, name)

    def test_default_query_string_is_empty(self, app):
        # WHY: most listings render without a search box; pin the
        # default so callers don't have to pass ``q=""`` explicitly.
        with app.test_request_context():
            ds = BaseDataSource(model_class=object)
        assert ds.q == ""

    def test_get_order_by_targets_created_at_descending(self, app):
        # WHY: pins the *default sort* contract — newest-first. The
        # expression must compile down to ``created_at DESC``.
        with app.test_request_context():
            ds = BaseDataSource(model_class=_FakeModel, q="")
            ordering = ds.get_order_by()
        # SQLAlchemy descending expressions expose ``modifier`` set to
        # the ``desc_op`` operator. Stringification is the most robust
        # check across SA versions.
        assert "DESC" in str(ordering).upper()
        assert "created_at" in str(ordering)


class TestBaseTableClassAttributes:
    """Pin class-level invariants that don't need a request context."""

    def test_inherits_from_table(self):
        # WHY: structural — ``Table.render`` and friends are inherited;
        # breaking the parent link silently disables templates.
        assert issubclass(BaseTable, Table)

    def test_dom_id_is_articles_table(self):
        # WHY: ``id = "articles-table"`` is the HTMX target id; the
        # JS/HTMX side relies on a *stable* class-level constant.
        assert BaseTable.id == "articles-table"

    def test_columns_is_a_property(self):
        # WHY: the override comment explicitly notes "property-over-
        # property"; pin it so a refactor doesn't silently turn it into
        # a class variable (which would freeze it for all instances).
        assert isinstance(BaseTable.__dict__["columns"], property)


class TestBaseTableGetColumns:
    """Pin the *shape* of the column list — order, labels, css class."""

    @pytest.fixture
    def table(self, app):
        with app.test_request_context():
            yield BaseTable(_FakeModel, q="")

    def test_column_order_is_titre_status_created_actions(self, table):
        # WHY: rendering order is visually significant; pin the exact
        # left-to-right ordering of the four columns.
        names = [c["name"] for c in table.get_columns()]
        assert names == ["titre", "status", "created_at", "$actions"]

    def test_actions_column_uses_sentinel_name(self, table):
        # WHY: ``$actions`` is a magic name handled by ``Row.get_cells``
        # to skip rendering as a normal cell. Pin the exact spelling.
        actions = [c for c in table.get_columns() if c["name"] == "$actions"]
        assert len(actions) == 1
        assert actions[0]["label"] == ""

    def test_titre_column_has_truncate_class(self, table):
        # WHY: the truncate CSS class on the title column is the
        # reason long titles don't blow up the table layout.
        titre = next(c for c in table.get_columns() if c["name"] == "titre")
        assert "truncate" in titre["class"]
        assert "w-full" in titre["class"]

    @pytest.mark.parametrize(
        ("name", "expected_label"),
        [
            ("titre", "Titre"),
            ("status", "Statut"),
            ("created_at", "Création"),
        ],
    )
    def test_column_labels_are_french(self, table, name, expected_label):
        # WHY: localised labels are part of the UI contract; pinning
        # them catches accidental translation drift.
        col = next(c for c in table.get_columns() if c["name"] == name)
        assert col["label"] == expected_label

    def test_property_delegates_to_method(self, table):
        # WHY: pin that ``table.columns`` and ``table.get_columns()``
        # are equivalent — subclasses that override one but not the
        # other would otherwise drift silently.
        assert table.columns == table.get_columns()


class TestBaseTableGetActions:
    """Pin the action list contract built per row."""

    @pytest.fixture
    def table(self, app):
        with app.test_request_context():
            t = BaseTable(_FakeModel, q="")
        # Replace ``url_for`` with a recording stand-in so we can
        # assert that the correct action argument is forwarded.
        t.url_for = lambda item, action="get", **kw: f"/x/{item.id}/{action}"
        return t

    def test_returns_view_edit_delete_in_order(self, table):
        # WHY: action ordering controls the visual order of buttons /
        # menu items; pin it.
        actions = table.get_actions(_ItemStub(id=42))
        labels = [a["label"] for a in actions]
        assert labels == ["Voir", "Modifier", "Supprimer"]

    def test_each_action_has_a_url(self, table):
        # WHY: every action dict must have a non-empty URL or the
        # template will render broken links.
        for action in table.get_actions(_ItemStub(id=7)):
            assert action["url"]

    @pytest.mark.parametrize(
        ("index", "url_suffix"),
        [
            (0, "/get"),  # "Voir" uses the default ``url_for`` action
            (1, "/edit"),
            (2, "/delete"),
        ],
    )
    def test_url_for_action_argument_is_correct(self, table, index, url_suffix):
        # WHY: the default "Voir" link omits the action arg and relies
        # on the ``url_for`` default of ``"get"``; edit/delete must
        # forward their action explicitly. Pin that wiring.
        actions = table.get_actions(_ItemStub(id=99))
        assert actions[index]["url"].endswith(url_suffix)


class TestBaseTableGetMediaName:
    """Defensive: ``get_media_name`` must never raise."""

    @pytest.fixture
    def table(self, app):
        with app.test_request_context():
            yield BaseTable(_FakeModel, q="")

    def test_returns_media_name_when_present(self, table):
        item = _ItemStub(media=_NamedStub("Le Figaro"))
        assert table.get_media_name(item) == "Le Figaro"

    def test_returns_empty_when_media_is_none(self, table):
        item = _ItemStub()
        item.media = None
        assert table.get_media_name(item) == ""

    def test_returns_empty_when_media_attribute_absent(self, table):
        # WHY: the implementation uses ``getattr(obj, "media", None)``
        # so an object *without* a ``media`` attribute at all must
        # still return ``""`` (not raise ``AttributeError``).
        class _NoMedia:
            pass

        assert table.get_media_name(_NoMedia()) == ""


class TestMakeDatasourceHook:
    """The ``_make_datasource`` hook is documented as the override
    point for bug 0132 (Sujet visibility scoping). Pin that subclasses
    can swap the datasource without re-implementing ``__init__``."""

    def test_subclass_can_swap_datasource(self, app):
        # WHY: this is the *only* documented extension point and the
        # whole reason the hook exists. Verify the override is honoured.
        sentinel = object()

        class _Subclass(BaseTable):
            def _make_datasource(self, model_class, q):
                return sentinel

        with app.test_request_context():
            table = _Subclass(_FakeModel, q="x")

        assert table.data_source is sentinel
        # And the query string is still recorded on the table itself.
        assert table.q == "x"

    def test_default_hook_returns_base_datasource(self, app):
        # WHY: without an override the table must wire up the generic
        # datasource — pin the default behaviour.
        with app.test_request_context():
            table = BaseTable(_FakeModel, q="")
        assert isinstance(table.data_source, BaseDataSource)
        assert table.data_source.model_class is _FakeModel
