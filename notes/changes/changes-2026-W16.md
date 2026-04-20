# Changes Week 16, 2026

## SWORK Members - New Filters

Several new filters added to the SWORK members list:

- "Type organisation"
- "Type entreprise presse et media"
- "Type presse & média"
- "Types de PR Agencies"
- "Tailles d'organisation"

Additional improvements:

- Filters now correctly handle accentuated values
- Filter lists restricted to active (non-deleted) users
- New `KYCProfile.type_agence_rp` property

## Avis d'Enquête

- Popup added to confirm refusal of RDV dates by expert
- Missing mail message for RDV refusal now sent
- New case handled: "Refusé, suggestion"
- UX fix: no longer need to select "no date" radio button when clicking "Refuse les dates"

## BW Cleanup

- Removed deprecated implementation of BW gallery images
- Renamed "Nom officiel" to "name"

## Organisation Utils

- Refactored query for AUTO organisations
- Small refactor of `organisation_utils.py`

## Tests

- Updated tests across multiple modules:
  - `admin/test_utils.py`
  - `admin/test_invitations.py`
  - `admin/test_org_email_utils.py`
  - `admin/test_show_org.py`
  - `bw/test_user_utils.py`
  - `test_organisation_utils.py`
- Fixed failing tests

## Infrastructure

- Bump version 2026.04.16.1
- Dependencies updated
- Linter (ty) hints applied
