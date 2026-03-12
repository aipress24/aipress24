# Changes Week 11, 2026

## Organisation/BusinessWall Refactoring

### BW as Source of Truth for Organisation Data

The Organisation model now uses BusinessWall as the authoritative source for display data (logo, cover image, etc.) instead of storing duplicate data on Organisation.

### Image URL Functions

- Added `get_organisation_logo_url(org)` utility function
  - Returns logo URL from active BusinessWall if available
  - Falls back to Organisation's own logo
  - Returns default placeholder if no logo found
- Added `get_organisation_cover_image_url(org)` utility function
  - Same pattern as logo URL function
- Removed deprecated `Organisation.logo_image_signed_url()` method
- Removed deprecated `Organisation.cover_image_signed_url()` method

### BusinessWall Lookup Functions

- Renamed `get_business_wall_for_organisation()` to `get_active_business_wall_for_organisation()`
  - Only returns BW with active status
- Added `get_any_business_wall_for_organisation()`
  - Returns BW regardless of status (for admin/debug purposes)
- Organisation type (AUTO or specific) is now updated when creating/cancelling a BW

### SWORK Module Updates

- Organisation list now displays logo from active BusinessWall
- Organisation profile page uses BW information (WIP)
- Organisation list filter uses only BW source data

### Menu Changes

- Removed "New Business Wall" from WORK menu
- "Business Wall" menu item now links directly to new BW class

### Export/Cleanup

- Removed deprecated Organisation fields from ODF export
- Removed deprecated commented lines throughout codebase
- Updated Organisation detail page to show correct fields

## Tests

### New Tests

- Added test for `get_organisation_logo_url()`
- Added test for `get_organisation_cover_image_url()`

### Test Fixes

- Fixed tests for WIP menu items (after menu restructure)
- Fixed tests for Organisation list filter (BW source)
- Fixed tests for cover image URL
- Fixed tests for organisation logo URL

## Technical Documentation

### Type Hints Guide

Created `notes/dev/type-hints.md` covering:
- Modern Python type hints (Optional, Union, `|` syntax)
- SQLAlchemy 2.0 patterns (Mapped, mapped_column)
- When to use `TYPE_CHECKING` to avoid circular imports
- Examples for relationships and nullable fields

### N+1 Detector Documentation

Created `notes/dev/n-plus-one-detector.md` covering:
- How to use the N+1 query detector middleware
- Detection and correction examples
- Integration in development workflow
- Test integration with `--n-plus-one` flag

### CLAUDE.md Updates

- Added `ty` as primary type checker
- Documented `pyrefly` as alternative type checker
- Updated type checking workflow instructions

## CI/CD

### Type Checking

- Verified `ty check src/app` is already integrated via `make lint`
- GitHub Actions runs `nox -e lint` which includes `ty check`
- SourceHut builds run `uv run make lint` which includes `ty check`

### N+1 Detection in Tests

- Added `--n-plus-one` pytest option (logs warnings on detection)
- Added `--n-plus-one-strict` pytest option (fails tests on detection)
- Added `assert_no_n_plus_one` fixture for explicit N+1 checking in specific tests
- Configuration via `TestConfig`: `N_PLUS_ONE_ENABLED`, `N_PLUS_ONE_THRESHOLD`, `N_PLUS_ONE_RAISE`

## Code Review

### Module Audits

Created `notes/audits/audit-biz-events-2026-w10.md` with code review findings:

**Module `biz` (Marketplace)**
- 4 high priority issues identified
- 8 medium priority issues identified
- Fixed: removed frozen object mutation in `biz/components/biz_card.py`

**Module `events`**
- 6 high priority issues identified
- 7 medium priority issues identified

### SQLAlchemy 2.0 Migration Assessment

Created `notes/backlog/sqlalchemy-2.0-migration.md` with:
- Current status: 65-70% complete
- 16 migration tasks identified
- Prioritized task list with file paths and line numbers
- Pattern conversion reference guide

## Module Wire - Cleanup

- Removed commented ComTab code from `_tabs.py`
- Removed dead `WireCommonMixin` class (never used)
- Added comment explaining why `image_id` has no FK (polymorphic reference)
- Cleaned up unused imports

## Bug Fixes

- Fixed ontology cache replaced by TTL cache (10min, 1h for city list)
- Added dependency on `cachetools` library

## Code Quality

- Applied linter fixes throughout codebase
- Various simplification refactoring
