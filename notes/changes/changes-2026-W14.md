# Changes Week 14, 2026

## Image Copyright Tooltips

Copyright info now surfaced as tooltips throughout the app : BW gallery, organisation profile (logo + banner), user profile (photo + banner). Long captions wrap on multiple lines ; carousel tooltips show without delay.

## Promotions Fixes

- Missing route added (was triggering "Une erreur de communication est survenue").
- Trix editor can now manage images in promotions.

## BWType Refactoring

- `BWType` moved to `app.enums` (single source of truth) ; deprecated `BWTypeEnum` removed.
- Deprecated `Organisation.bw_type` field + migration removed.
- `OrgPublicationsTab.guard` uses `org.bw_active`.

Tests temporarily disabled in W12 (during the Organisation model simplification) re-enabled : guard tests (`test_guard_false_for_auto`, `test_guard_true_for_non_auto`, `test_guard_true_for_media_bw`), `OrgPublicationsTab` tests, AUTO-organisation invitation tests.

## Organisation Utils — BW Type Integration

- `get_organisation_family()` updated to use BW type.
- `get_organisation_for_noms_medias()` and similar updated.
- New `is_organisation_an_agency(org)` to distinguish media from agency in WIRE tabs.
- ODS export updated to the new organisation model.

## Deleted Organisation Cleanup

- A deleted Organisation now has no remaining BW reference (`bw_id` + `bw_active` reset).
