# Changes Week 14, 2026

## Image Copyright Tooltips

Copyright information is now displayed as tooltips across the application:
- BW gallery images: caption + copyright shown on hover
- Organisation profile: logo and banner image copyright
- User profile: photo and banner image copyright
- Long captions formatted on multiple lines
- Carousel tooltips display without delay

## Promotions Fixes

- Fixed missing route that caused "Une erreur de communication est survenue" error
- Trix editor can now manage images in promotions

## BWType Refactoring

### Enum Consolidation

- `BWType` moved to `app.enums` module (single source of truth)
- Removed deprecated `BWTypeEnum`
- Removed deprecated `Organisation.bw_type` field + migration
- `OrgPublicationsTab.guard` now uses `org.bw_active`

### Re-enabled Tests

All tests temporarily disabled in week 12 during the Organisation model simplification are now re-enabled:
- Guard tests (`test_guard_false_for_auto`, `test_guard_true_for_non_auto`, `test_guard_true_for_media_bw`)
- `OrgPublicationsTab` tests
- Invitation tests (organisation AUTO)

## Organisation Utils - BW Type Integration

- `get_organisation_family()` updated to use BW type
- `get_organisation_for_noms_medias()` and similar functions updated
- New `is_organisation_an_agency(org)` function to distinguish media from agency in WIRE tabs
- ODS data export updated to reflect new organisation model

## Deleted Organisation Cleanup

- Ensure deleted Organisation has no remaining BW reference (`bw_id`, `bw_active` reset)
