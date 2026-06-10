# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for wip/components/table/table.py table-level pure logic.

Scope: DataSource ABC contract, Table delegation/defaults, Row identity
caching + cell building + actions delegation, and Table.url_for routing
through the dict/object overloads of app.flask.routing.url_for. The Cell
class is already covered by test_table_cell.py and is NOT retested here.
Pagination.render() and get_template() require Flask app/request context
and are integration-level concerns - intentionally out of scope.
"""

from __future__ import annotations

import re

import pytest

from app.modules.wip.components.table.table import (
    Cell,
    DataSource,
    Pagination,
    Row,
    Table,
)


class StubDataSource(DataSource):
    """Concrete DataSource for exercising Table delegation."""

    def __init__(
        self,
        items: list | None = None,
        count: int = 0,
        offset: int = 0,
        limit: int = 10,
    ) -> None:
        self._items = items or []
        self._count = count
        self.offset = offset
        self.limit = limit

    def get_items(self) -> list:
        return self._items

    def get_count(self) -> int:
        return self._count


class StubItem:
    """Duck-typed row item with arbitrary attributes."""

    def __init__(self, **kwargs) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


def _make_table(
    columns: list[dict] | None = None,
    items: list | None = None,
    actions=None,
) -> Table:
    """Build a Table bound to a stub data source for tests."""
    table = Table()
    table.data_source = StubDataSource(items=items or [])
    # `columns` is declared as a ClassVar on Table for the production
    # default ; assigning via object.__setattr__ shadows it on the
    # instance only — which is the test intent.
    object.__setattr__(table, "columns", columns or [])
    if actions is not None:
        table.get_actions = actions  # type: ignore[method-assign]
    return table


class TestDataSourceContract:
    """DataSource is an ABC: enforces get_items/get_count on subclasses."""

    def test_cannot_instantiate_abstract_base(self) -> None:
        # Pinning the ABC: instantiating DataSource directly must fail,
        # so callers are forced to provide a concrete implementation.
        with pytest.raises(TypeError):
            DataSource()  # type: ignore[abstract]

    def test_partial_subclass_cannot_instantiate(self) -> None:
        # Implementing only one of the two abstract methods leaves the
        # class abstract; this guards against accidental partial impls.
        class OnlyItems(DataSource):
            def get_items(self) -> list:
                return []

        with pytest.raises(TypeError):
            OnlyItems()  # type: ignore[abstract]

    def test_full_subclass_instantiates_and_delegates(self) -> None:
        # The happy path: a fully-implemented subclass works and exposes
        # the offset/limit attributes that Pagination relies on.
        ds = StubDataSource(items=["a", "b"], count=2, offset=5, limit=10)
        assert ds.get_items() == ["a", "b"]
        assert ds.get_count() == 2
        assert ds.offset == 5
        assert ds.limit == 10


class TestTableDelegation:
    """Table forwards reads to its data source and exposes safe defaults."""

    def test_get_items_delegates_to_data_source(self) -> None:
        # Table.get_items must not filter or copy - it returns whatever
        # the data source returns. This is a thin pass-through contract.
        items = [StubItem(name="x"), StubItem(name="y")]
        table = _make_table(items=items)
        assert table.get_items() is items

    def test_get_items_returns_empty_list_when_source_empty(self) -> None:
        # Empty data source must still yield an iterable (defensive: the
        # render() path iterates this to build Row objects).
        table = _make_table(items=[])
        assert table.get_items() == []

    def test_get_actions_default_is_empty_list(self) -> None:
        # The base Table provides NO actions by default. Subclasses must
        # opt in by overriding. Regressions here would silently render
        # action columns for every table that hasn't customised them.
        table = _make_table()
        assert table.get_actions(StubItem()) == []

    def test_pagination_property_returns_bound_pagination(self) -> None:
        # The pagination property is a factory: each access returns a
        # fresh Pagination wired to this exact table instance.
        table = _make_table()
        pag = table.pagination
        assert isinstance(pag, Pagination)
        assert pag.table is table

    def test_pagination_property_is_not_cached(self) -> None:
        # Defensive: confirm we get distinct instances. If someone later
        # adds @cached_property this test will flag the behaviour change.
        table = _make_table()
        assert table.pagination is not table.pagination


class TestTableUrlFor:
    """Table.url_for routes through app.flask.routing.url_for overloads."""

    def test_url_for_dict_with_url_key(self) -> None:
        # The dict overload of url_for short-circuits to the "_url" key
        # without requiring a Flask request context.
        table = _make_table()
        assert table.url_for({"_url": "/items/42"}) == "/items/42"

    def test_url_for_object_with_url_attribute(self) -> None:
        # The default singledispatch branch falls through to obj._url
        # when present, again with no Flask context dependency.
        table = _make_table()
        obj = StubItem(_url="/things/7")
        assert table.url_for(obj) == "/things/7"

    def test_url_for_object_without_url_attribute_raises(self) -> None:
        # Defensive: an item that lacks both registration and _url must
        # raise RuntimeError - silent failures would hide template bugs.
        table = _make_table()
        with pytest.raises(RuntimeError):
            table.url_for(StubItem())

    def test_url_for_ignores_action_and_kwargs(self) -> None:
        # _action / **kwargs are accepted by Table.url_for for callers
        # that pass them, but the dict overload ignores them entirely.
        table = _make_table()
        result = table.url_for({"_url": "/x"}, _action="edit", foo="bar")
        assert result == "/x"


class TestRowIdentity:
    """Row.id must be a stable, lazily-generated hex uuid per instance."""

    def test_row_id_is_32_char_hex_string(self) -> None:
        # Row.id must look like uuid4().hex - 32 lowercase hex chars.
        # Templates rely on this format for DOM ids.
        table = _make_table()
        row = Row(table, StubItem())
        assert re.fullmatch(r"[0-9a-f]{32}", row.id)

    def test_row_id_is_cached(self) -> None:
        # Accessing .id twice returns the same value. Each access creates
        # a uuid on miss, so caching prevents DOM id churn between calls.
        table = _make_table()
        row = Row(table, StubItem())
        first = row.id
        second = row.id
        assert first == second
        assert row.cache["id"] == first

    def test_distinct_rows_have_distinct_ids(self) -> None:
        # Two Row instances must not collide - the uuid space makes this
        # statistically certain but the contract should still be pinned.
        table = _make_table()
        ids = {Row(table, StubItem()).id for _ in range(5)}
        assert len(ids) == 5

    def test_row_id_honours_preseeded_cache(self) -> None:
        # The cache dict is exposed via attrs; passing a pre-populated
        # cache must short-circuit the uuid path. This is what makes the
        # render pipeline safe to call .id from multiple template loops.
        table = _make_table()
        row = Row(table, StubItem(), cache={"id": "preseeded"})
        assert row.id == "preseeded"


class TestRowCells:
    """Row.get_cells filters $actions columns and wraps the rest in Cell."""

    def test_get_cells_skips_actions_pseudo_column(self) -> None:
        # The "$actions" column is rendered via get_actions(), not as a
        # data cell. get_cells() MUST drop it so templates don't double
        # up the action column.
        columns = [
            {"name": "title"},
            {"name": "$actions"},
            {"name": "status"},
        ]
        table = _make_table(columns=columns)
        row = Row(table, StubItem(title="t", status="s"))
        cells = row.get_cells()
        assert [c.column["name"] for c in cells] == ["title", "status"]

    def test_get_cells_preserves_column_order(self) -> None:
        # Templates iterate cells in declaration order. Verify that
        # get_cells() does not reorder columns even when none are
        # filtered out.
        columns = [{"name": "a"}, {"name": "b"}, {"name": "c"}]
        table = _make_table(columns=columns)
        row = Row(table, StubItem(a=1, b=2, c=3))
        assert [c.column["name"] for c in row.get_cells()] == ["a", "b", "c"]

    def test_get_cells_returns_cell_instances_bound_to_item(self) -> None:
        # Each cell must reference the row's item and the matching column
        # dict by identity - Cell.render() reads attributes off item.
        item = StubItem(title="hello")
        column = {"name": "title", "class": "wide"}
        table = _make_table(columns=[column])
        row = Row(table, item)
        cells = row.get_cells()
        assert len(cells) == 1
        assert isinstance(cells[0], Cell)
        assert cells[0].item is item
        assert cells[0].column is column

    def test_get_cells_with_no_columns_returns_empty(self) -> None:
        # Edge: empty column list yields empty cell list (not None, not
        # an error). Lets callers safely iterate the result.
        table = _make_table(columns=[])
        row = Row(table, StubItem())
        assert row.get_cells() == []

    def test_get_cells_with_only_actions_column_returns_empty(self) -> None:
        # Edge: if every column is "$actions" the row has no data cells.
        # The action column rendering happens via get_actions instead.
        table = _make_table(columns=[{"name": "$actions"}])
        row = Row(table, StubItem())
        assert row.get_cells() == []


class TestRowActions:
    """Row.get_actions forwards to Table.get_actions with the row's item."""

    def test_get_actions_delegates_with_item(self) -> None:
        # Row.get_actions must call table.get_actions with this row's
        # item, not some shared/global value. Pin this via a recording
        # stub so we catch any future refactor that loses the item arg.
        seen: list = []

        def record(item):
            seen.append(item)
            return [{"label": "Edit"}]

        item = StubItem(id=1)
        table = _make_table(actions=record)
        row = Row(table, item)
        actions = row.get_actions()
        assert actions == [{"label": "Edit"}]
        assert seen == [item]

    def test_get_actions_default_when_table_not_customised(self) -> None:
        # When the Table subclass hasn't overridden get_actions, the
        # default empty list propagates through Row unchanged.
        table = _make_table()
        row = Row(table, StubItem())
        assert row.get_actions() == []


class TestPaginationBinding:
    """Pagination is constructed with the owning table reference only."""

    def test_pagination_keeps_reference_to_table(self) -> None:
        # The Pagination dataclass holds the table for later access to
        # data_source.offset/limit/count. Pin the binding so a refactor
        # that copies values instead of holding the table is detected.
        table = _make_table()
        pag = Pagination(table)
        assert pag.table is table
