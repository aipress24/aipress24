# Changes Week 12, 2026

## Organisation Model — Major Simplification

`Organisation.type` had drifted out of sync with BusinessWall types. Simplification : Organisation now mirrors its BW directly, no parallel state.

- New `Organisation.bw_active` : copy of the BW type, updated at every BW activation / deactivation point.
- New `Organisation.bw_id` : ID of the associated BW (no FK to avoid model-tree reorganisation).
- `Organisation.is_auto` now derived from `bw_id` instead of the deprecated `type`.
- `get_active_business_wall_for_organisation()` uses `Organisation.bw_id` directly (with fallback for test compatibility).
- Both fields set at BW creation, reset on cancellation / suspension.
- Deprecated `Organisation.type` attribute removed ; admin templates updated ; "type" column dropped from exports ; guards / tests migrated to `bw_active`.
- Migration accounts for existing BWs (no data loss).

Remaining work : not every organisation-by-type usage is yet coherent ; some media / expert lists may still be wrong ; some tests still to reactivate.

## BusinessWall — Geographic Attributes

- New `BW.zip_code`, `city`, `department` fields + migration.
- Auto-calculated from address ; city-name parsing fixed.
- `pays_zip_ville` stored even when empty ; current zipcode / city values now displayed.

## Administration

BW direct management by admin :

- New `is_bw_manager_or_admin()` helper.
- App admin can now manage any BW.
- "Modify BW information" in `admin/show_org` redirects to the BW dashboard as admin (with confirmation popup).

`admin/show_org` cleanup : "List managers" and "List dirigeants" removed ; page adapted to the new BW classes ; duplicate `OrgVM` code removed ; BW deletion check added before Organisation deletion.

## BW Role Management

- Remove-from-list button for BWMi / BWPRi (removal from invitation list no longer deletes accepted users) ; re-invitation of a deleted manager allowed.
- BW role invitations now surfaced in user invitations list.
- Pre-check : user must have a non-deleted Organisation before subscribing to a BW.

## User Publications

- User's communiqués displayed in the publications tab.

## Organisation List

- BW name displayed in the organisations list (WIP).
- Fix for SQLite (missing `split_part` function).
- Tests updated.

## Audit biz / events — Priorities 1 & 2 Completed

Per `notes/audits/audit-biz-events-2026-w10.md`.

**Priority 1 (Security / Data Integrity)** :

- `biz/views/item.py` : 404 if item not PUBLIC.
- `events/views/_filters.py` : form-data validation with `match/case` guards + `raise BadRequest`.

**Priority 2 (Performance)** :

- Eager loading in `biz/views/item.py` (`selectinload(MarketplaceContent.owner).selectinload(User.profile)`) and `events/views/_common.py:get_comments()` (`selectinload(Comment.owner)`).
- `biz/views/home.py` : DISTINCT queries for filters instead of loading all objects.
- `events/services.py` : multi-column `order_by` support via tuple.

`match/case` refactor : `wire/views/_filters.py`, `admin/views/_common.py` / `validation.py`, `bw_activation/routes/` (4 files), `wip/crud/cbvs/` (3 files), `wip/views/business_wall_registration.py`.

Type improvements : `TypedDict` for `FilterSpec` / `TabSpec` in `biz/views/_common.py` ; `assert` → `TypeError` in `events/services.py:get_participants()` (+ unit tests with order_by + limit) ; type hints on `BizCard.obj`, `BizTabs.tabs`, `EventListVM.extra_attrs`, `EventDetailVM.extra_attrs`, `DateFilter.apply` ; dead code (`biz/components/biz_list.py`) removed ; `assert` → proper exceptions in `events/views/_common.py`.

## Tests — Major Refactoring

Clear separation : integration tests (direct function calls) vs E2E tests (HTTP routes via FlaskClient). FlaskClient tests migrated `tests/b_integration/` → `tests/c_e2e/`.

New integration tests (`tests/b_integration/modules/bw/test_bw_invitation_integration.py`) : 6 test classes covering `invite_user_role`, `revoke_user_role`, `ensure_roles_membership`, `apply_bw_missions_to_pr_user`, `sync_all_pr_missions`, `invite_pr_provider`.

New E2E tests (`tests/c_e2e/modules/bw/`) : `test_confirm_role_invitation.py` (8 tests), `test_confirm_partnership_invitation.py` (7 tests).

E2E fixture simplification : `fresh_db` + `db_session` consolidated in `tests/c_e2e/conftest.py` (redundant `modules/conftest.py` removed) ; all E2E tests use `fresh_db` autouse. **584 E2E tests + 114 BW integration tests passing.**

## Test Coverage

**Module BW (40 % → 46 %)** : `test_dashboard.py` (8 tests), `test_stage1.py` (12 tests). Per-file : `dashboard.py` 41→97 %, `not_authorized.py` 62→100 %, `stage1.py` 31→97 %.

**Module WIP (61 % → 70 %+)** : 7 E2E test files (40 tests covering home, dashboard, newsroom, comroom, eventroom, publications, business_wall) ; 3 integration test files (`test_expert_filter.py` 10 tests, `test_expert_selectors.py` 32 tests, `test_business_wall_forms.py` 44 tests). Per-file gains : `home.py` 58→100 %, `dashboard.py` 42→92 %, `newsroom.py` 36→94 %, `comroom.py` 50→100 %, `eventroom.py` 52→100 %, `publications.py` 62→100 %, `business_wall.py` 21→85 %. **319 WIP tests total**.

## Bug Fixes

- Type errors + missing imports + CI adjustments.
- Stripe webhook deprecated endpoint fixed.
- Organisation reputation calculation (temporary fix).
- `OrgVM` description + site_url fixed.
- "Published by CPPAP press agency" line removed from post cards.
