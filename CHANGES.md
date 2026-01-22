# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Avis Enquête: confirmation popups for RDV acceptance, decline, and proposal actions
- Avis Enquête: ability to decline all proposed RDV dates
- Avis Enquête: status messages for opportunities ("Attente de dates", "Opportunité déclinée", "Nouvelle opportunité")
- Avis Enquête: auto-update status from draft to public when sent to experts
- Avis Enquête: flash message shows number of new experts contacted
- Avis Enquête: Opportunity URL now included in proposal emails
- Explicit logging of sender, recipient, subject, and status for emails
- Mail limiter increased to 20 mails / 7 days
- CLI: `flask roles list` and `flask users list` commands
- Unit tests for mailers
- E2E tests for expert RDV refusal workflow

### Changed

- Reorganized Flask CLI commands into logical groups (29 → 21 top-level commands):
  - `data`: bootstrap-users, fetch-bootstrap-data, load-db, upgrade-ontologies
  - `media`: dump-photos, upload-photos
  - `dev`: debug, check, components, packages
  - `fix`: roles, test-user
- Mailers: renamed `sender_name` → `sender_mail`, added `sender_full_name` field

### Fixed

- WIP module Table pagination
- Opportunities page refresh when redirecting to self with HTMX
- Avis Enquête redirect to wip.opportunities after RDV response
- Email sender name now included in logged mail information
- Access to opportunity page now restricted to the expert only
- Suppressed pkg_resources deprecation warning and logging noise in CLI

## [VERSION] - DATE

### Changed

### Fixed

### Documentation
