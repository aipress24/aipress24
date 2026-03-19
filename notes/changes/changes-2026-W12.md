# Changes Week 12, 2026

## Organisation Model - Major Simplification

### Context

The `Organisation.type` attribute was no longer in sync with BusinessWall types. This caused inconsistencies between organisation types and BW types.

### New Organisation Attributes

- Added `bw_active` field: copy of the BW type, systematically updated at BW activation/deactivation points
- Added `bw_id` field: ID of associated BusinessWall, simplifies access to BW from Organisation
- Both fields are localized (no FK to avoid model tree reorganization)

### Benefits

- Guarantees Organisation is in sync with BW (or AUTO)
- Avoids joins when listing organisations by type (e.g., media organisations list)
- `Organisation.is_auto` now based on `bw_id` content instead of deprecated `type`

### Optimizations

- `get_active_business_wall_for_organisation()` now uses `Organisation.bw_id` directly
- Fallback to old method for test compatibility

### BW Lifecycle Management

- `bw_active` and `bw_id` set at BusinessWall creation
- `bw_active` and `bw_id` reset on BW cancellation/suspension

### Deprecated Code Removal

- Removed `Organisation.type` attribute
- Updated admin/show_org templates
- Removed "type" column from Organisation exports
- Updated guards and tests to use `bw_active`

### Migration

- Migration script accounts for existing BWs (no data loss in production)

### Remaining Work

- Organisation type usage by BW type not yet coherent everywhere
- Some organisation lists by type (media, expert) may be incorrect
- Tests to reactivate

## BusinessWall - Geographic Attributes

### New BW Fields

- Added `zip_code`, `city`, `department` attributes to BusinessWall model
- Database migration for new fields
- Automatic calculation of zip code, department, city from address
- Fixed city name parsing
- Store `pays_zip_ville` even when empty
- Display of current zipcode/city values now functional

## Administration

### BW Direct Management by Admin

- New `is_bw_manager_or_admin()` function
- Allows app admin to manage any BW directly
- Admin/show_org: "Modify BW information" redirects to BW dashboard as admin with confirmation popup

### Admin/show_org Cleanup

- Removed "List managers" and "List dirigeants"
- Adapted page to new BW classes
- Removed duplicate OrgVM code
- BW deletion check before Organisation deletion

## BW Role Management

### Invitation Improvements

- Button to remove BWMi/BWPRi from list (removing from invitation list no longer deletes accepted users)
- Allow re-inviting a deleted BW manager
- Added BW role invitations to user invitations list

### Fixes

- Check user has non-deleted Organisation before subscribing to BW

## User Publications

- Display user's Communiqués in publications tab

## Organisation List

- Display BW name in organisations list (WIP)
- Fix for SQLite (missing `split_part` function)
- Updated organisation list tests

## Audit biz/events - Priorities 1 & 2 Completed

See `notes/audits/audit-biz-events-2026-w10.md`

### Priority 1 (Security/Data Integrity) ✅

- Status verification in `biz/views/item.py` - returns 404 if item not PUBLIC
- Form data validation in `events/views/_filters.py` - uses `match/case` with guards and `raise BadRequest`

### Priority 2 (Performance) ✅

- Eager loading in `biz/views/item.py` - `selectinload(MarketplaceContent.owner).selectinload(User.profile)`
- Eager loading in `events/views/_common.py:get_comments()` - `selectinload(Comment.owner)`
- Refactoring `biz/views/home.py` - DISTINCT queries for filters instead of loading all objects
- ORDER BY SQL in `events/services.py` - tuple `order_by` support for multi-column sorting

### match/case Refactoring

Converted all `if action ==` patterns to `match/case` in:
- `wire/views/_filters.py`, `admin/views/_common.py`, `admin/views/validation.py`
- `bw/bw_activation/routes/` (confirm_role_invitation, confirm_partnership_invitation, stage_b4, stage_b6)
- `wip/crud/cbvs/` (events, articles, communiques)
- `wip/views/business_wall_registration.py`

### Type Improvements

- Added `TypedDict` for `FilterSpec` and `TabSpec` in `biz/views/_common.py`
- Replaced `assert` with `TypeError` in `events/services.py:get_participants()`
- Unit tests for `get_participants()` with order_by and limit
- Type hints added: `BizCard.obj`, `BizTabs.tabs`, `EventListVM.extra_attrs()`, `EventDetailVM.extra_attrs()`, `DateFilter.apply()`
- Removed dead code: `biz/components/biz_list.py`
- Replaced `assert` with proper exceptions in `events/views/_common.py`

## Tests - Major Refactoring

### E2E vs Integration Reorganization

- Clear distinction: integration tests (direct function calls) vs E2E tests (HTTP routes via FlaskClient)
- Migrated FlaskClient tests from `tests/b_integration/` to `tests/c_e2e/`

### New Integration Tests

`tests/b_integration/modules/bw/test_bw_invitation_integration.py`:
- `TestInviteUserRoleIntegration` - RoleAssignment creation
- `TestRevokeUserRoleIntegration` - role deletion
- `TestEnsureRolesMembershipIntegration` - role cleanup
- `TestApplyBwMissionsToPrUserIntegration` - mission application
- `TestSyncAllPrMissionsIntegration` - PR mission synchronization
- `TestInvitePrProviderIntegration` - partnership creation

### New E2E Tests

`tests/c_e2e/modules/bw/`:
- `test_confirm_role_invitation.py` - 8 tests for role invitation routes
- `test_confirm_partnership_invitation.py` - 7 tests for partnership invitation routes

### E2E Fixture Simplification

- Consolidated `fresh_db` and `db_session` in `tests/c_e2e/conftest.py`
- Removed `tests/c_e2e/modules/conftest.py` (redundant)
- All E2E tests now use `fresh_db` automatically via autouse
- 584 E2E tests pass, 114 BW integration tests pass

### Other Test Fixes

- Fixed BW tests in PostgreSQL environment
- Temporarily disabled typeguard tests

## Test Coverage Improvements

### Module BW (40% → 46%)

- `test_dashboard.py` (8 tests): dashboard, reset, not_authorized routes
- `test_stage1.py` (12 tests): index, confirm_subscription, select_subscription, activation_choice, information
- Coverage: `dashboard.py` 41%→97%, `not_authorized.py` 62%→100%, `stage1.py` 31%→97%

### Module WIP (61% → 70%+)

**E2E Tests** (`tests/c_e2e/modules/wip/`):
- `test_home_views.py` (5 tests): role-based redirection
- `test_dashboard_views.py` (6 tests): dashboard access and content
- `test_newsroom_views.py` (5 tests): newsroom access and item filtering
- `test_comroom_views.py` (4 tests): comroom access for PRESS_RELATIONS
- `test_eventroom_views.py` (4 tests): eventroom access
- `test_publications_views.py` (7 tests): publications JSON data
- `test_business_wall_views.py` (9 tests): org-profile access and POST actions

Coverage improvements:
- `home.py` 58%→100%
- `dashboard.py` 42%→92%
- `newsroom.py` 36%→94%
- `comroom.py` 50%→100%
- `eventroom.py` 52%→100%
- `publications.py` 62%→100%
- `business_wall.py` 21%→85%

**Integration Tests** (`tests/b_integration/modules/wip/`):
- `test_expert_filter.py` (10 tests): filtering logic, state management, MAX_SELECTABLE_EXPERTS
- `test_expert_selectors.py` (32 tests): FilterOption, all selectors (Secteur, Metier, Fonction, Competences, TypeOrganisation, TailleOrganisation, Langues, Pays, Departement, Ville)
- `test_business_wall_forms.py` (44 tests): BWFormGenerator, merge_org_results, field helpers, ValidBWImageField

Coverage improvements:
- `business_wall_fields.py` 58%→100%
- `valid_bw_image.py` 48%→100%
- `business_wall_form.py` 10%→75%

**Total: 319 WIP tests (E2E + integration)**

## Bug Fixes

- Fixed type errors
- Fixed missing imports
- Adjusted CI configuration
- Code cleanup and formatting
- Fixed Stripe webhook (deprecated endpoint)
- Fixed organisation reputation calculation (temporary)
- Fixed OrgVM for description and site_url
- Removed "published by CPPAP press agency" display from post cards
