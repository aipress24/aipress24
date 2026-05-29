# Changes Week 11, 2026

## Organisation / BusinessWall Refactoring

BW becomes the source of truth for Organisation display data (logo, cover image).

- New helpers `get_organisation_logo_url(org)` and `get_organisation_cover_image_url(org)` : look at the active BW first, fall back to the Organisation's own image, then a default placeholder.
- Deprecated `Organisation.logo_image_signed_url()` and `cover_image_signed_url()` removed.
- `get_business_wall_for_organisation()` renamed `get_active_business_wall_for_organisation()` (status check) ; added `get_any_business_wall_for_organisation()` for admin / debug.
- Organisation type (AUTO vs specific) now updated when creating / cancelling a BW.

SWORK updates :

- Organisation list shows BW logo ; filter uses only BW source data ; org profile uses BW info (WIP).

Menu :

- "New Business Wall" removed from WORK menu ; "Business Wall" menu item now links directly to the new BW class.

Export / cleanup : deprecated Org fields removed from ODF export ; deprecated commented lines removed ; Organisation detail page shows correct fields.

## Tests

- New tests : `get_organisation_logo_url()`, `get_organisation_cover_image_url()`.
- Fixed : WIP menu items, Organisation list filter, cover image URL, organisation logo URL.

## Technical Documentation

- New `notes/dev/type-hints.md` : modern Python type hints (Optional, Union, `|`), SQLAlchemy 2.0 patterns, TYPE_CHECKING, relationships + nullables.
- New `notes/dev/n-plus-one-detector.md` : usage, detection examples, dev workflow, pytest `--n-plus-one` integration.
- CLAUDE.md updated : `ty` documented as primary type checker, `pyrefly` as alternative.

## CI/CD

- `ty check src/app` already integrated via `make lint` ; GitHub Actions + SourceHut both run it.
- New pytest options : `--n-plus-one` (log warnings), `--n-plus-one-strict` (fail tests). `assert_no_n_plus_one` fixture for explicit checks. Config via `TestConfig`.

## Code Review

`notes/audits/audit-biz-events-2026-w10.md` produced. Findings :

- **biz (Marketplace)** : 4 high, 8 medium. Fixed : frozen object mutation in `biz/components/biz_card.py`.
- **events** : 6 high, 7 medium (deferred).

SQLAlchemy 2.0 migration assessment in `notes/backlog/sqlalchemy-2.0-migration.md` : 65-70 % complete ; 16 prioritised tasks with file paths + line numbers + pattern conversion reference.

## Module Wire — Cleanup

- Commented `ComTab` code removed from `_tabs.py`.
- Dead `WireCommonMixin` removed.
- `image_id` no-FK explained (polymorphic reference).
- Unused imports cleaned.

## Bug Fixes

- Ontology cache replaced by TTL cache (10 min, 1 h for city list) ; `cachetools` added.
- Linter fixes throughout ; misc simplification.
