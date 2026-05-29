# Changes Week 7, 2026

## Business Wall Activation Module

Major integration of the BW activation workflow into the main app.

- BW activation pages integrated into the WIP module ; "New BW" entry in WIP secondary menu links to the activation dashboard.
- AUTO organisations in SWORK redirect to the new BW registration page.
- All BW activation pages require authenticated user ; BW layout shares header / footer with the KYC wizard.
- User data pre-loaded in nomination contacts form ; name, firstname, email read-only during activation. Best BWType auto-guessed from user profile. `user.metier_fonction` added to BW user context. `BWType` enum used consistently.
- Free BW creation : initial implementation in progress.
- Blueprint renamed `bw_activation_full` → `bw_activation` ; file hierarchy reorganised, POC reset button removed, BW models simplified.
- DB : new migration for BW activation tables ; removed deprecated KYC temp blob table ; metadata merging fixed (no more circular imports) ; BW model tables now properly detected.

## Flask View Refactoring — `MethodView` Pattern

Systematic refactor of Flask views handling both GET and POST into single `MethodView` classes.

- Admin (users, orgs, groups, contents, promotions, show_user, show_org, validation), Preferences (profile, banner, contact, interests, invitations), WIP (business_wall_registration).
- "Useless existence" tests removed (`test_*_function_exists`, `test_*_view_class_exists`, `test_*_method_exists`) ; kept the ones verifying behaviour.

## Bug Fixes

- SWORK wall messages : route link fixed.
- Avis Enquête ciblage : inactive users filtered out.
- Opportunities : "liste des opportunités" link added on detail page.
- File handling : Path vs file object confusion fixed.
- BW templates : `bw_info.allows_self_management` defaults to false.

## Infrastructure & Tooling

- New `scripts/check_s3.py` : end-to-end S3 bucket test (upload / verify / download / cleanup) using Flask config.
- CI updates ; `test_wip_views` allows `bw_activation` endpoint prefix.
- Dependency updates (with one revert) ; ruff fixes on enums, imports, dict keys ; dead imports + type-checking false positives cleaned up.
