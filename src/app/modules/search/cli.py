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

import click
import svcs.flask
from flask.cli import with_appcontext
from flask_super.cli import group
from rich import print
from sqlalchemy import select

from app.flask.extensions import db

from .adapters import is_public, to_doc
from .engine import SearchEngine
from .registry import REGISTRY


@group(short_help="Manage the wesh-backed search index")
def search() -> None:
    pass


@search.command(short_help="Drop and rebuild the index from the database")
@with_appcontext
def rebuild() -> None:
    counts = rebuild_index()
    total = sum(counts.values())
    for type_name, count in counts.items():
        print(f"  [cyan]{type_name}[/cyan]: {count}")
    print(f"[green]Indexed {total} document(s)[/green]")


def rebuild_index() -> dict[str, int]:
    """Drop the index and re-walk the database. Returns the count
    indexed per source type. Exposed as a function so the background
    scheduler (and any other automation) can reuse it.

    The doc-level ``type`` discriminator comes from ``adapters.doc_type(obj)``,
    so polymorphic bases (e.g. ``MarketplaceContent``) fan out into
    their concrete subclass discriminators automatically.
    """
    engine = svcs.flask.container.get(SearchEngine)
    engine.reset()

    counts: dict[str, int] = {}
    for entry in REGISTRY:
        count = 0
        stmt = select(entry.model).execution_options(yield_per=500)
        for obj in db.session.scalars(stmt):
            if not is_public(obj):
                continue
            engine.upsert(to_doc(obj))
            count += 1
        counts[entry.source_type] = count
    return counts


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
