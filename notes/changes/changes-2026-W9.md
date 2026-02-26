# Changes Week 9, 2026

## Business Wall - Role Invitations

### Email Notification System

- Added `BWRoleInvitationMail` mailer class for BW role invitations
- Added `send_role_invitation_mail()` function to send invitation emails
- BWMI (internal manager) invitation with email and role assignment
- BWPRI (internal PR) invitation with email and role assignment

### Role Confirmation

- Added confirmation page for BW role invitations (`confirm_role_invitation`)
- Uses redirect pattern for role confirmation flow
- Better display of pending invitations lists

### Role Management Improvements

- `bw_managers_ids()` now uses generic `bw_roles_ids()` function
- Added support for BWME (external manager) role management
- `ensure_roles_membership()` ensures all role assignments are for current organisation members
- Filter user lists by `user.active` status

## Business Wall - PR Agency Partnerships

### Partnership Model Changes

- Partnership now uses `BusinessWall.id` to reference partner (not `Organisation.id`)
- Added migration to update Partnership references
- Added `BusinessWall.name` field and `BusinessWall.name_safe` property
- Use `BusinessWall.name_safe` in early stages of BW registration

### PR Agency Lists

- `get_current_press_relation_bw_list()` - list of current PR agency partnerships
- `get_pending_press_relation_bw_list()` - list of pending PR invitations
- `get_press_relation_bw_list()` - general PR BW list
- `bw_pr_managers_ids()` - get PR manager user IDs
- `get_current_pr_bw_info_list()` - display full name and email in PR agencies list
- `get_pending_pr_bw_info_list()` - pending PR BW info with contact email

### Partnership Invitation Workflow

- Rewrote BW PR invitation workflow using Partnership invitation status
- Added specific confirmation page for Partnership invitations
- Show pending, rejected, and expired invitations for partnerships
- Do not show PR BW with status "invited" in list of available PR BWs
- `invite_pr_provider()` function using `invite_user_role()`
- Display pending PR BW list in B04_manage_external_partners.html

### UI Improvements

- Specific message and inactive button if no PR agency in list for BWPRe
- Display list of current BW PR external partners
- Adapted block numbers in dashboard for PR BW (skip block 4, renumber block 5 to 4)

## Business Wall - Paid Activation

- Added `create_new_paid_bw_record()` function for paid BW creation
- Added links to CGV and "Accord de diffusion" on pricing page
- Added CGV and "Accord de diffusion" for BW confirmation page
- Removed "Retour choix d'activation" links from paid confirmation pages

## Bug Fixes

- Fixed `non_authorized` → `not_authorized` endpoint name typo (3 files)
- Fixed page B05_assign_missions.html when BW does not have newsroom feature
- Fixed `get_pending_press_relation_bw_list()` to return actual BW of assigned user
- Fixed `get_pending_pr_bw_info()` to actually return value
- Fixed BW PR retrieval in confirmation page
- Fixed typing issue in wire module filters (added `callable()` check)

## Tests

### Integration Tests

- Added comprehensive BW integration tests in `tests/b_integration/modules/bw/`
- Split large test file into focused modules:
  - `conftest.py` - shared fixtures
  - `test_bw_activation.py` - activation utilities and scenarios
  - `test_bw_routes.py` - activation route tests
  - `test_stages_b1_b3.py` - internal management stages
  - `test_stages_b4_b6.py` - external management stages
  - `test_bw_dashboard.py` - dashboard and workflow tests
- Mocked `send_role_invitation_mail` to avoid email sending in tests
- Fixed tests by creating active users and setting `g.user` where needed

### Unit Tests

- Added test for `BWRoleInvitationMail` mailer
- Added test for `ensure_roles_membership()`
- Added tests for `change_bwmi_emails()` and `change_bwpri_emails()`
- Added test for `bw_pr_managers_ids()`
- Added tests for `get_current_press_relation_bw_list()`
- Added tests for `get_pending_press_relation_bw_list()`
- Added test for `create_new_paid_bw_record()`

## Code Quality

- Removed debug symbols and unused code
- Applied linter fixes
- Updated dependencies
