# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Mini-CMS CLI commands.

- `flask cms seed` : import every `static-pages/*.md` into the
  `CorporatePage` table. Idempotent — existing slugs are skipped
  unless `--overwrite` is passed.

Spec: `local-notes/specs/corporate-pages-cms.md`.
"""

from __future__ import annotations

from pathlib import Path

import click
import toml
from flask import current_app
from flask.cli import with_appcontext
from flask_super.cli import group
from svcs.flask import container

from app.flask.extensions import db
from app.modules.admin.cms import CorporatePageService


@group(name="cms", short_help="Mini-CMS utilities")
def cms() -> None:
    """Mini-CMS utilities."""


@cms.command("seed")
@click.option(
    "--overwrite",
    is_flag=True,
    default=False,
    help="Replace existing DB entries with file contents.",
)
@with_appcontext
def seed(overwrite: bool) -> None:
    """Import every `static-pages/*.md` file into the DB.

    Safe to re-run ; without `--overwrite` existing slugs are kept.
    """
    root = Path(current_app.root_path).parent.parent.parent / "static-pages"
    svc = container.get(CorporatePageService)

    created = 0
    overwritten = 0
    skipped = 0

    for md_file in sorted(root.glob("*.md")):
        slug = md_file.stem
        data = md_file.read_text()
        try:
            head, body = data.split("---", 1)
        except ValueError:
            click.echo(f"  skip {slug}: missing TOML header separator")
            skipped += 1
            continue
        metadata = toml.loads(head.strip())
        title = metadata.get("title", slug)
        body_md = body.lstrip("\n")

        existing = svc.get(slug=slug)
        if existing is None:
            svc.upsert(slug=slug, title=title, body_md=body_md)
            click.echo(f"  created {slug}")
            created += 1
        elif overwrite:
            svc.upsert(slug=slug, title=title, body_md=body_md)
            click.echo(f"  overwritten {slug}")
            overwritten += 1
        else:
            click.echo(f"  skip {slug} (already in DB)")
            skipped += 1

    db.session.commit()
    click.echo(
        f"Done: created={created}, overwritten={overwritten}, skipped={skipped}"
    )
