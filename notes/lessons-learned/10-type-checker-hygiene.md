# Type Checker Hygiene

Part of [Lessons Learned](00-index.md).

### `case Path(template_path):` is a fake pattern match

**Rule**: never trust a positional `case` pattern on a stdlib type without `__match_args__`.

`pathlib.Path` has none; the branch raises `TypeError` at runtime the first time it's hit. Correct form: `case Path() as template_path:`. Pyrefly catches this, mypy doesn't.

### Prefer stdlib `enum.StrEnum` over `aenum.StrEnum`

**Rule**: pyrefly flags `not-iterable` and `not-a-type` on `aenum` subclasses; stdlib behaves identically for `StrEnum + auto()`.

### `type: ignore` outlives the tool that justified it

**Rule**: always use `type: ignore[specific-code]`, and audit them whenever you change checkers.

Migrating mypy → ty dropped 23 ignores, most dating from SQLAlchemy patterns long since fixed. The same happened again when `ty` gained a `redundant-cast` diagnostic: two casts labelled "work around a mypy bug" had outlived the bug, each dragging an extra `type: ignore` with it.

### Prefer an annotated local binding to a suppression

**Rule**: when a checker misreads a framework descriptor, bind the value to an annotated local instead of silencing a whole error code.

`mode: EventMode = self.mode` states what is true and keeps the checker's coverage everywhere else. Pyrefly has no SQLAlchemy support, so instance access on a mapped column types as `InstrumentedAttribute[T]` — the binding is the honest fix.
