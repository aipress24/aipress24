# Changes Week 10, 2026

## Business Wall - Data Entry Form

### Identity Fields

- Added `name` field for BW display name
- Added `name_official` for official organisation name
- Added `name_group` for group/holding name
- Added `name_institution` for institution name

### Contact Fields

- Added `tel_standard` for main phone number
- Added `postal_address` for postal address
- Added `site_url` for website URL

### Location Fields

- Added `geolocalisation` field
- Added country/code/city location fields

### Organisation Fields

- Added `type_organisation` dual field with migration
- Added `taille_organisation` for organisation size
- Added `type_entreprise_media` for media company type
- Added `type_pr_agency` for PR agency type

### Editorial Fields

- Added `positionnement_editorial` for editorial positioning
- Added `audience_cible` for target audience
- Added `type_presse_media` for press/media type
- Added `periodicite` for publication frequency (requires ontology entry)

### Interest Fields

- Added `interest_political_detail` for political interests
- Added `interest_economics_detail` for economic interests
- Added `interest_association_detail` for association interests
- Added multi-select fields for "centre d'intérêt" (political, economics, association)

### Activity Fields

- Added `secteur_activite_couvert` for covered activity sectors
- Added `clients` field for client list

### Image Management

- Added `cover_image` (bandeau) as second image item
- Added `gallery_images` field to BusinessWall model
- Added gallery image management (add/remove multiple images)
- Added related utilities for gallery handling

### Form Improvements

- Added generic `updateDualMultiSelect()` JavaScript function for dual selection fields
- Added `permit_selection_of_dual_field_type_organisation()` in BW forms
- Removed BW form field for "liste des membres"

## Business Wall - PR Missions

### Missions Storage

- Added `missions` field to BusinessWall model to store stage 6 missions as dict
- Added migration script for BusinessWall `missions` field

### Mission Functions

- Added `apply_bw_missions_to_pr_user()` to apply BW missions to PR user
- Added `sync_all_pr_missions()` to synchronize all PR permissions when changing missions
- Apply BW missions to BWPRe when accepting role (using PR owner.id)
- Apply BW missions to new BW PR when accepting role

### Permission Handling

- Use `PermissionType` enum for permission names in BW stage 6
- Store PR missions in BusinessWall model
- Sync current PR permissions when changing missions to PR for BW

## Bug Fixes

- Fixed "Enregistrer et continuer" button to actually send to next page
- Removed mention at bottom of BW form
- Fixed single session commit in BW data management
- Removed bad import
- Removed wrong attribute in BusinessWall
- Fixed `PermissionType` values
- Fixed BW stage 6 missions code

## Module Swork - Cleanup

### Constants

- Added `SWORK_LIST_LIMIT = 100` constant in `settings.py`
- Replaced hardcoded `.limit(100)` with `SWORK_LIST_LIMIT` in:
  - `components/members_list.py`
  - `components/organisations_list.py`
  - `components/groups_list.py`

### Placeholder URLs

- Fixed hardcoded placeholder URLs in `views/group.py`
- Now uses `group.logo_url` with fallback to `/static/img/blank-square.png`
- Now uses `group.cover_image_url` with fallback to `/static/img/gray-texture.png`

### Documentation

- Added docstrings to `BaseList` class
- Added docstrings to `Filter` class
- Added docstrings to `FilterByCity` class
- Added docstrings to `FilterByDept` class
- Added docstrings to `MembersList` class
- Added docstrings to `OrganisationsList` class
- Added docstrings to `GroupsList` class

## Tests & Coverage

### New Test Files

- `tests/a_unit/flask/lib/pywire/test_routes.py` (6 tests)
  - `TestLivewireSyncInput`: Tests for setting simple and nested attributes via dot notation
  - `TestLivewireFireEvent`: Tests for event firing with dash-to-underscore conversion

- `tests/a_unit/flask/cli/test_nav.py` (9 tests)
  - `TestCreateMockUserWithRoles`: Tests for creating mock users with roles
  - `TestMockUserHasRole`: Tests for role checking with enum and string
  - `TestResolveFilterUser`: Tests for filter user resolution

- `tests/a_unit/services/stripe/test_stripe_utils.py` (17 tests)
  - `TestCheckStripeKeys`: Tests for Stripe key validation
  - `TestGetStripeConfig`: Tests for Stripe config retrieval
  - `TestLoadPricingTableId`: Tests for pricing table ID loading

- `tests/a_unit/services/pdf/test_pdf_base.py` (4 tests)
  - `TestToPdf`: Tests for PDF conversion base function

- `tests/a_unit/flask/lib/test_htmx.py` (4 tests)
  - `TestExtractFragment`: Tests for HTMX fragment extraction

- `tests/a_unit/flask/lib/test_controllers.py` (9 tests)
  - `TestDecorators`: Tests for `@get`, `@post`, `@route` decorators
  - `TestDispatcher`: Tests for Dispatcher class
  - `TestControllerDecorator`: Tests for `@controller` decorator

### Testing Documentation

- Created `notes/dev/testing.md` with best practices and antipatterns
- Covers: stubs vs mocks, pure functions, ViewModels, transaction isolation
- Documents functional core / imperative shell pattern for database testing

### Test Refactoring

- Renamed `test_utils.py` to `test_stripe_utils.py` to avoid pytest import collisions
- Renamed `test_base.py` to `test_pdf_base.py` for same reason
- Fixed ClassVar type error in `swork/components/base.py`

## DevOps

- Added Docker configuration (`Dockerfile`, `docker-compose.yml`)
- Added Hop3 configuration

## Code Quality

- Misc cleanup and refactoring
- Applied linter fixes
