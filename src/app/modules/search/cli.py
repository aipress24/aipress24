"""``flask search …`` CLI for operating the wesh-backed search index.

Three subcommands:

* ``rebuild`` — drop every indexed document, then re-walk the database
  and re-index every post for which ``is_public`` is True. Use after a
  schema change, when content drifted from the index, or to bootstrap
  a fresh environment.

* ``status`` — print the document count per indexed type. Useful to
  confirm the rebuild worked.

* ``query <qs>`` — run a search from the shell. Mostly for debugging
  ranking and operator queries.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import click
import svcs.flask
from flask.cli import with_appcontext
from flask_super.cli import group
from rich import print
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from sqlalchemy import func, select

from app.flask.extensions import db

from .adapters import is_public, to_doc
from .engine import SearchEngine
from .registry import REGISTRY

if TYPE_CHECKING:
    from collections.abc import Iterator

    from .registry import IndexableType


@group(short_help="Manage the wesh-backed search index")
def search() -> None:
    pass


@search.command(short_help="Drop and rebuild the index from the database")
@click.option(
    "--quiet",
    is_flag=True,
    default=False,
    help="Suppress the progress bar (useful for cron / scripts).",
)
@with_appcontext
def rebuild(quiet: bool) -> None:
    counts = rebuild_index(show_progress=not quiet)
    total = sum(counts.values())
    for type_name, count in counts.items():
        print(f"  [cyan]{type_name}[/cyan]: {count}")
    print(f"[green]Indexed {total} document(s)[/green]")


def rebuild_index(*, show_progress: bool = True) -> dict[str, int]:
    """Drop the index and re-walk the database. Returns the count
    indexed per source type. Exposed as a function so the background
    scheduler (and any other automation) can reuse it.

    Each indexable type is walked once and bulk-upserted under a
    single wesh writer transaction (one commit per type rather than
    one per document — orders of magnitude faster).

    ``show_progress=False`` is for non-interactive callers (the
    scheduler) and tests, where the Rich progress bar adds noise.
    """
    engine = svcs.flask.container.get(SearchEngine)
    engine.reset()

    counts: dict[str, int] = {}
    if show_progress:
        with _progress_bar() as progress:
            for entry in REGISTRY:
                counts[entry.source_type] = _rebuild_one_type(engine, entry, progress)
    else:
        for entry in REGISTRY:
            counts[entry.source_type] = _rebuild_one_type(engine, entry, None)
    return counts


def _progress_bar() -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn("[cyan]{task.fields[type_name]:>18}[/cyan]"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("[dim]rows[/dim]"),
        TimeElapsedColumn(),
    )


def _rebuild_one_type(
    engine: SearchEngine,
    entry: IndexableType,
    progress: Progress | None,
) -> int:
    """Walk every row of ``entry.model``, keep the public ones, and
    bulk-upsert them. The progress bar advances per *scanned* row
    (not per indexed row), so the user sees forward motion even when
    most rows fail ``is_public``.
    """
    total = db.session.scalar(select(func.count()).select_from(entry.model)) or 0
    task_id = None
    if progress is not None:
        task_id = progress.add_task("", total=total, type_name=entry.source_type)

    indexed = 0

    def public_docs() -> Iterator[dict]:
        nonlocal indexed
        stmt = select(entry.model).execution_options(yield_per=500)
        for obj in db.session.scalars(stmt):
            if progress is not None and task_id is not None:
                progress.advance(task_id)
            if is_public(obj):
                indexed += 1
                yield to_doc(obj)

    engine.bulk_upsert(public_docs())
    return indexed


@search.command(short_help="Show document counts per type")
@with_appcontext
def status() -> None:
    engine = svcs.flask.container.get(SearchEngine)
    print(f"[bold]Total:[/bold] {engine.doc_count()}")
    # Iterate doc-types (not source-types) so polymorphic buckets like
    # marketplace report per-subtype counts.
    for entry in REGISTRY:
        for doc_type_name in entry.doc_types:
            count = engine.doc_count(type=doc_type_name)
            print(f"  [cyan]{doc_type_name}[/cyan]: {count}")


@search.command(short_help="Run a search from the CLI (debug)")
@click.argument("qs")
@click.option("--type", "type_filter", default=None, help="Restrict to a type")
@click.option("--limit", default=20, type=int)
@with_appcontext
def query(qs: str, type_filter: str | None, limit: int) -> None:
    engine = svcs.flask.container.get(SearchEngine)
    hits = engine.search(qs, type=type_filter, limit=limit)
    if not hits:
        print("[yellow]No results[/yellow]")
        return
    for hit in hits:
        print(f"[bold]{hit.get('title', '')}[/bold]  ({hit.get('type')})")
        print(f"  id={hit.get('id')} url={hit.get('url')}")
