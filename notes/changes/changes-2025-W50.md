# Changes Week 50, 2025

## Email Rate Limiting

New rate-limiting layer to prevent email abuse and stay within sending quotas.

- New `EmailLog` model + migration `add_table_email_log.py` to count emails sent over a window.
- `email_limiter.py` with rate-limit logic, integrated into the email service ; configuration moved to `constants.py`.

## Organisation Images Migration to S3

Continuation of the S3 migration : Business Wall (BW) organisation images now use `FileObject`.

- `Organisation.cover_image` and `logo_image` columns → `FileObject` (replaces blob storage). Migration added for the BW logo column.
- Widgets adapted for BW logo / cover upload + display.
- Faker generator for Orgs updated to the new image format.

## Refactoring

- `file_object_utils.py` moved to shared `lib/` ; `_deserialize_file_object()` made public as `deserialize_file_object()`.
- Unused `BlobService` removed from WIP.
- `flush()` vs `commit()` fix in `email_limiter.py`.

## Testing

- More tests added on the admin module.
- Version bump : 2025.12.15.1.
