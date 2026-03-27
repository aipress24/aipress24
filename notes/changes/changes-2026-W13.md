# Changes Week 13, 2026

## Image Cropping - All Content Types

Image cropping (client-side recadrage) has been deployed across all content types in the application.

### Articles

- Article images can now be cropped before upload
- New utility function `extract_image_from_request()` for consistent image handling
- Retrieval of original filename from uploaded images
- Improved UI for article image forms

### Communiqués & Events

- Same crop feature and UI applied to Communiqués and Events
- Removed legacy Stimulus test code from events template

### KYC / User Profile

- Crop widget for carte de presse photo
- Merged KYC image widgets into unified component
- New square photo form in KYC
- Photo portrait copyright now optional
- New `User.photo_image_copyright` field + migration
- KYC model updated to version 45

## BusinessWall - Image Management

### Copyright Fields

- New `logo_image_copyright` and `cover_image_copyright` fields on BusinessWall model
- Database migration for new fields
- Integrated into BW forms
- Crop support for BW logo and cover images

### Gallery (New Feature)

- New `BWImage` model for managing BW gallery images
- Database migration for BWImage
- `signed_url()` method on BWImage for direct S3 content access
- Gallery management forms in BW dashboard
- `MAX_GALLERY_IMAGES` constant (10) with enforcement
- Image numbering starts from 1 (applied to all galleries: BW, articles, communiqués, events)
- BW gallery images displayed in Organisation slider (SWORK)
- Removed deprecated organisation screenshot reference in SWORK

### Other BW Fixes

- Corrected numbering of BW registration steps

## Infrastructure

- Hop3 deployment configuration (work in progress)
- Dependency updates

## Tests

- New E2E tests for ontology/taxonomy manager (27 tests, coverage 54% → 96%)
- Improved MinIO availability detection: now verifies credentials (via `boto3.list_buckets()`) in addition to TCP connectivity, properly skipping storage-dependent tests when MinIO is unavailable or misconfigured
