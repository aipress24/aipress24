# Changes Week 16, 2026

## SWORK Members — New Filters

5 new filters on the members list : "Type organisation", "Type entreprise presse et media", "Type presse & média", "Types de PR Agencies", "Tailles d'organisation".

- Filters now correctly handle accented values.
- Filter lists restricted to active (non-deleted) users.
- New `KYCProfile.type_agence_rp` property.

## Avis d'Enquête

- Popup to confirm refusal of RDV dates by the expert.
- Missing RDV-refusal mail now sent.
- New "Refusé, suggestion" case handled.
- UX : no longer need to tick the "no date" radio when clicking "Refuse les dates".

## BW Cleanup

- Deprecated implementation of BW gallery images removed.
- "Nom officiel" renamed to "name".

## Organisation Utils

- Refactored query for AUTO organisations ; small refactor of `organisation_utils.py`.

## Tests

- Updates across `admin/test_utils.py`, `admin/test_invitations.py`, `admin/test_org_email_utils.py`, `admin/test_show_org.py`, `bw/test_user_utils.py`, `test_organisation_utils.py`.
- Failing tests fixed.

## Infrastructure

- Version bump 2026.04.16.1 ; deps update ; linter (`ty`) hints applied.
