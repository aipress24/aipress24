# Changes Week 50, 2025

## Email Rate Limiting

A new **email rate limiting** feature was added to prevent email abuse and ensure compliance with sending limits.

### Key Changes

**1. EmailLog Table**
- New `EmailLog` model to track emails sent over time
- Enables counting emails sent during a specific period

**2. Email Limiter Service**
- Added `email_limiter.py` with rate limiting logic
- Integrated into the email service
- Configuration moved to `constants.py`

### Database Migration
- `add_table_email_log.py` - Creates the EmailLog table

## Organisation Images Migration to S3

Continuing the S3 migration effort, **Business Wire (BW) organisation images** now use `FileObject` storage.

### Key Changes

**1. Model Changes**
- Organisation `cover_image` and `logo_image` columns now use `FileObject`
- Replaces previous blob-based storage

**2. Widget Adaptation**
- Updated widgets for BW logo and cover image upload/display

**3. Fake Data Generator**
- Updated fake generator for Orgs to work with new image format

### Database Migration
- Migration script for BW logo image column

## Refactoring

**1. File Object Utilities**
- Moved `file_object_utils.py` to shared `lib/` directory
- Renamed `_deserialize_file_object()` to public `deserialize_file_object()`

**2. Cleanup**
- Removed unused `BlobService` from WIP module
- Fixed `flush()` vs `commit()` usage in email_limiter.py

## Testing

- Added more tests for the admin module

## Commits

### Email Rate Limiting
- `deb888dd` - feat: add EmailLog table to be able to count mail sent during a period of time
- `113fbd6e` - chore: add migration script for table EmailLog
- `bce82902` - feat: add email_limiter.py
- `1643453c` - feat: use email_limiter in email service
- `2284aed4` - refact: move email limiter to constants.py

### Organisation S3 Migration
- `d5abe95f` - feat: use S3/FileObject for BW cover and logo image
- `4049a891` - chore: add migration for BW logo image
- `3016b09e` - chore: change Organisation column for FileObject
- `fd85ec11` - t: adapt widget for BW logo and cover image
- `547c3b37` - fix: update fake generator for Orgs

### Refactoring
- `67bda925` - refact: move lib/file_object_utils.py -> ../../lib/file_object_utils.py
- `e87af00a` - refact: rename _deserialize_file_object() deserialize_file_object()
- `d9c21c6a` - fix: remove unused BlobService from module WIP
- `e5ee36bf` - fix: fix tests by using flush() instead of commit() in email_limiter.py

### Testing & Misc
- `3e75682d` - tests: more tests for the admin module
- `731b0ff4` - chore: format
- `2a68a4b8` - Bump version (2025.12.15.1)
