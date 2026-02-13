# Changes Week 7, 2026

## Business Wall Activation Module

Major integration of the Business Wall (BW) activation workflow into the main application.

### New Registration Flow

- Integrated BW activation pages into the WIP module
- Added "New BW" entry in WIP secondary menu linking to activation dashboard
- AUTO organisations in SWORK list now redirect to the new BW registration page
- All BW activation pages require authenticated user

### User Experience

- BW layout now uses same header/footer styling as KYC wizard
- Current user data pre-loaded in nomination contacts form
- Users cannot modify name, firstname, or email during BW activation (read-only)
- System automatically guesses best BWType based on user profile

### User Data

- Added `user.metier_fonction` to BW user data context
- BWType configuration now uses `BWTYPE` enum consistently

### Free BW Creation (WIP)

- Initial implementation for creating free Business Wall subscriptions

### Module Organization

- Renamed blueprint from `bw_activation_full` to `bw_activation`
- Reorganized module file hierarchy, removed unused components
- Removed POC reset button from activation interface
- Simplified BW models structure

### Database

- New migration: add BW activation tables
- New migration: remove deprecated KYC temp blob table
- Fixed metadata merging to prevent circular imports
- Ensured BW activation model tables are properly detected

## Flask View Refactoring

Systematic refactoring of Flask views to use `MethodView` pattern.

### Modules Refactored

- **Admin module**: users, orgs, groups, contents, promotions, show_user, show_org, validation
- **Preferences module**: profile, banner, contact, interests, invitations
- **WIP module**: business_wall_registration

### Pattern Applied

Views handling both GET and POST consolidated into single `MethodView` classes:

```python
# Before: separate functions
@blueprint.route("/page", methods=["GET"])
def page_get(): ...

@blueprint.route("/page", methods=["POST"])
def page_post(): ...

# After: single MethodView class
class PageView(MethodView):
    def get(self): ...
    def post(self): ...
```

### Test Cleanup

Removed useless existence tests that only checked if functions/classes exist:
- `test_*_function_exists`
- `test_*_view_class_exists`
- `test_*_method_exists`

Kept tests that verify actual behavior and configuration.

## Bug Fixes

- **SWORK Wall Messages**: Fixed route link for wall messages
- **Avis Enquête Ciblage**: Filter out users with inactive status
- **Opportunities**: Added link to "liste des opportunités" in detailed opportunity page
- **File Handling**: Fixed confusion between Path and file objects
- **BW Templates**: Default `bw_info.allows_self_management` to false

## Infrastructure & Tooling

### New Script

- `scripts/check_s3.py`: Test S3 bucket access by uploading/downloading a test file
  - Validates S3 configuration from Flask config
  - Performs upload, verify, download, and cleanup operations

### CI & Testing

- Updated pytest configuration in pyproject.toml
- CI configuration updates
- Fixed test_wip_views to allow `bw_activation` endpoint prefix

### Dependencies

- Updated dependencies with appropriate constraints
- Reverted problematic dependency update

## Code Quality

### Type Checking

- Fixed multiple type checking issues across codebase
- Added type ignores for false positives
- Improved type annotations

### Linting

- Fixed ruff warnings on enums
- Fixed ruff warnings on imports and dict keys
- Removed dead imports
