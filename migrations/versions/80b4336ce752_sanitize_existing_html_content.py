"""Sanitize HTML content stored before the SanitizedHTML column type

Bug #0126 v5: until commit 3dc9e783 (`|sanitize` filter on render) and
the SanitizedHTML column type, user-supplied HTML stored on multiple
content tables could contain `<script>`, event handlers, or
`javascript:` URLs. Templates that render via `|safe` (or that
previously used to) would have surfaced those payloads.

The filter neutralises them on read and the column type neutralises
them on write *going forward*. This migration back-fills the existing
data so the DB doesn't keep XSS payloads waiting to be re-rendered
by any code path that bypasses the filter.

Tables touched (every column carries the SanitizedHTML decorator):

- `cnt_base.content`          — BaseContent (ArticlePost, PressReleasePost,
                                EventPost, ShortPost, Comment, ...)
- `evr_event.contenu`         — Event (eventroom)
- `crm_communique.contenu`    — Communique (com'room)
- `nrm_article.contenu`       — Article (newsroom, via NewsroomCommonMixin)
- `nrm_sujet.contenu`         — Sujet
- `nrm_avis_enquete.contenu`  — AvisEnquete
- `nrm_commande.contenu`      — Commande
- `soc_group.description`     — Group (swork)
- `adm_promotion.body`        — Promotion (admin)

The sanitisation runs in Python (loaded via Alembic's app
bootstrapping), so we go batch-by-batch with the same `sanitize_html`
implementation the column type uses. Idempotent — re-running rewrites
already-clean rows to the same value.

Revision ID: 80b4336ce752
Revises: 9198ede3fe32
Create Date: 2026-05-13
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "80b4336ce752"
down_revision = "9198ede3fe32"
branch_labels = None
depends_on = None


# (table, column) pairs that now carry the SanitizedHTML type.
# Order doesn't matter — each is sanitised independently.
_HTML_COLUMNS: tuple[tuple[str, str], ...] = (
    ("cnt_base", "content"),
    ("evr_event", "contenu"),
    ("crm_communique", "contenu"),
    ("nrm_article", "contenu"),
    ("nrm_sujet", "contenu"),
    ("nrm_avis_enquete", "contenu"),
    ("nrm_commande", "contenu"),
    ("soc_group", "description"),
    ("adm_promotion", "body"),
)

# Process this many rows at a time. Big-table-friendly without
# blocking the whole release window on a single statement.
_BATCH_SIZE = 500


def upgrade() -> None:
    # Import inside the function so Alembic can run autogenerate
    # without booting the full Flask app.
    from app.services.html_sanitize import _sanitize_to_str

    conn = op.get_bind()
    for table, column in _HTML_COLUMNS:
        if not _table_has_column(conn, table, column):
            # Schema drift: column may not exist on this target. Skip
            # rather than fail the whole release. Tables without these
            # columns won't carry XSS payloads anyway.
            continue

        # We iterate by PK ranges so the migration survives concurrent
        # writes during a rolling deploy. Using `> last_id` instead of
        # OFFSET so the second pass doesn't re-scan rows already done.
        # The first pass omits the WHERE clause entirely: a typed
        # sentinel (`-2**63`) breaks against varchar PKs like
        # `adm_promotion.slug` (Postgres can't compare bigint > varchar).
        pk = _primary_key_column(conn, table)
        last_id = None
        while True:
            if last_id is None:
                query = text(
                    f"SELECT {pk}, {column} FROM {table} "
                    f"WHERE {column} IS NOT NULL "
                    f"ORDER BY {pk} LIMIT :batch"
                )
                params: dict = {"batch": _BATCH_SIZE}
            else:
                query = text(
                    f"SELECT {pk}, {column} FROM {table} "
                    f"WHERE {pk} > :last_id AND {column} IS NOT NULL "
                    f"ORDER BY {pk} LIMIT :batch"
                )
                params = {"last_id": last_id, "batch": _BATCH_SIZE}
            rows = conn.execute(query, params).fetchall()
            if not rows:
                break
            for row in rows:
                row_id, raw = row
                cleaned = _sanitize_to_str(str(raw))
                if cleaned != raw:
                    conn.execute(
                        text(
                            f"UPDATE {table} SET {column} = :cleaned "
                            f"WHERE {pk} = :pk"
                        ),
                        {"cleaned": cleaned, "pk": row_id},
                    )
                last_id = row_id
            if len(rows) < _BATCH_SIZE:
                break


def downgrade() -> None:
    # No reverse: we never want to restore the unsanitised content.
    # Even if a downgrade rolls back the SanitizedHTML decorators on
    # the models, the data should remain clean.
    pass


def _table_has_column(conn, table: str, column: str) -> bool:
    """True iff `table.column` exists in the current schema."""
    dialect = conn.dialect.name
    if dialect == "postgresql":
        result = conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = :t AND column_name = :c"
            ),
            {"t": table, "c": column},
        ).first()
        return result is not None
    # SQLite (used in tests) — PRAGMA returns one row per column.
    rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return any(r[1] == column for r in rows)


def _primary_key_column(conn, table: str) -> str:
    """Return the PK column name. Every table we touch has a single PK
    named either `id` (most) or `slug` (only `adm_promotion`)."""
    if table == "adm_promotion":
        return "slug"
    return "id"
