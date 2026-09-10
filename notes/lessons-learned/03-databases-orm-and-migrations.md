# Databases, ORM & Migrations

Part of [Lessons Learned](00-index.md).

### SQLite-green does not imply Postgres-green

**Rule**: any change touching schema, migrations, raw SQL, or type-sensitive operators (`>`, casts, JSON ops) must run `make test-postgres` before it counts as tested.

SQLite is permissive about types and tolerant of drift; Postgres is strict. An `EventPost.publisher_id` fix passed the whole SQLite suite, then crashed production with `UndefinedColumn`.

**The converse bites just as hard.** Hybrid-property expressions using `split_part` (Postgres-only) made the geographic filters of four modules return nothing on SQLite for months — hidden behind `except OperationalError: return []`, so they read as *empty* rather than *broken*. A green suite on either backend alone is close to no signal for anything dialect-sensitive.

### Portable SQL, or one construct that compiles per dialect

**Rule**: don't write dialect-specific SQL in a model. If a primitive genuinely differs, isolate it in one `@compiles` construct and share it.

`substr`, `||`, `coalesce`, `case` are common ground. Position search is not (`strpos` vs `instr`), nor is `->>` with an integer index — use SQLAlchemy's `col[key].as_string()`, which compiles for both. `app/lib/geoloc.py` is the worked example: one Python parser, one SQL builder, and a test asserting they agree on the same inputs.

### Hybrid property double API

**Rule**: a computed property that must be filterable needs `@hybrid_property` *plus* `.expression` — and the expression must be portable.

A plain `@property` reads in Python but breaks ORM filters. Beware the trap that follows: the Python half and the SQL half are two implementations of one rule, and they drift. Assert they agree, or derive both from one shared helper.

### `Mapped[dict]` vs `Mapped[list]` is not a typing cosmetic

**Rule**: pick the correct collection type — `ty` cascades 15+ errors when wrong.

Both are JSON columns at the DB level, but `ty` rejects `.append` and indexed iteration on a `Mapped[dict]`.

### `ClassVar` goes on the outside

**Rule**: `ClassVar[Mapped[...]]`, never `Mapped[ClassVar[...]]`.

Inverted, SQLAlchemy tries to map the static value.

### Compare by ID, not by instance, in `.where()`

**Rule**: `.where(Model.owner_id == user.id)` — never `.where(Model.owner == user)`.

The instance form works by accident; the ID form is explicit, avoids a relationship load, and doesn't break on detached instances.

### Keyset pagination must be PK-type-agnostic

**Rule**: never fabricate a "smaller than any value" sentinel — its type leaks.

A back-fill migration seeded `last_id = -(2**63)`, worked on 8 integer-PK tables, and exploded on a varchar PK: `operator does not exist: character varying > bigint`. Omit the `WHERE pk > …` clause on the first page (`last_id = None`), then switch to the bounded query.

### Empty-list filter trap

**Rule**: for optional SQL filters use `if authors:` — not `if authors is not None`.

`.where(Model.owner_id.in_([]))` matches nothing, silently. An empty list means "no filter", not "match nothing".

### Production commits at the view layer

**Rule**: routes commit; service helpers stay transaction-neutral.

The test harness wraps each test in a savepoint. A helper calling `db.session.commit()` leaks data past the rollback — caught late, by a table-emptiness check at teardown.

### Defaults apply at insert, not at construction

**Rule**: `mapped_column(default=…)` leaves the attribute `None` until the first flush. Seed it in an `init` listener if any code reads it before.

Validation that runs in the same transaction as creation — an API that builds and publishes without an intermediate flush — sees `None` where the annotation promises a value.
