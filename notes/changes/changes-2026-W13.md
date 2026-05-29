# Changes Week 13, 2026

## Image Cropping — All Content Types

Client-side recadrage deployed across all content surfaces.

- **Articles** : crop before upload. New `extract_image_from_request()` utility for consistent image handling ; original filename retrieved from uploads ; image-form UI improved.
- **Communiqués & Events** : same crop feature + UI. Legacy Stimulus test code removed from events template.
- **KYC / User Profile** : crop widget for carte-de-presse photo ; KYC image widgets merged into one component ; new square photo form ; photo portrait copyright now optional ; new `User.photo_image_copyright` field + migration ; KYC model bumped to version 45.

## BusinessWall — Image Management

Copyright fields :

- New `logo_image_copyright` and `cover_image_copyright` fields on BW + migration.
- Integrated into BW forms ; crop support for BW logo / cover.

Gallery (new feature) :

- New `BWImage` model + migration.
- `signed_url()` method on `BWImage` for direct S3 content access.
- Gallery management forms in the BW dashboard.
- `MAX_GALLERY_IMAGES = 10`, enforced.
- Image numbering starts at 1 (applied to all galleries : BW, articles, communiqués, events).
- BW gallery images displayed in Organisation slider (SWORK) ; deprecated `screenshot` reference removed.

Misc : BW registration step numbering corrected.

## Infrastructure & Tests

- Hop3 deployment configuration (WIP) ; dependency updates.
- 27 new E2E tests for ontology / taxonomy manager (coverage **54 % → 96 %**).
- `is_minio_available` improved : checks credentials via `boto3.list_buckets()` in addition to TCP — storage-dependent tests skip cleanly when MinIO is unavailable or misconfigured.
