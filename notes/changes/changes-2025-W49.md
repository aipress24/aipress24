# Changes Week 49, 2025

## User Photo Migration to S3

Following last week's S3 migration (articles, communiques, events), this week focused on migrating **user photos** to S3 storage using `FileObject`.

### Key Changes

**1. New Image Columns for Users**
- `user.photo_image`: profile photo stored in S3
- `user.cover_image`: cover image stored in S3
- `photo_carte_presse_image`: press card photo

**2. Database Migrations**
- `2d226d278d3b_add_column_user_cover_image.py`
- `8b0da77a7479_add_column_user_photo_image.py`
- `10aea8b9a3b4_add_column_photo_carte_presse_image.py`

**3. Data Migration Commands**
- Added Flask commands `dump_photos.py` and `load_photos.py` to migrate existing photos to S3

**4. KYC Views Adaptation**
- Refactored dynamic forms (`dynform`) to use `FileObject`
- Removed legacy `tmp blob` system
- Added `file_object_utils.py` for file serialization/deserialization
- Better handling of existing images (preserve if no new upload)

### Bug Fixes

- Fixed photo display in profiles
- Handled `None` values for missing photos
- Fixed `FileObject/dict` format in KYC views
- Fixed class attribute bug in `admin/pages/modif_users.py`

## Test Suite Improvements

### Major Test Refactoring

**1. Structure Reorganization**
- Moved "web" tests to `tests/c_e2e/` for better separation
- Converted mock-based tests to real e2e tests

**2. MinIO Configuration for Tests**
- MinIO initialization in `conftest.py`
- Support for both PostgreSQL and SQLite test runs

**3. Coverage Increase**
- **Coverage increased from 58% to 70%** (+12 percentage points)
- Added numerous unit tests
- Fixed bugs revealed by tests (commit/flush issues)

## Commits

### User Photo S3 Migration
- `75d142c9` - chore: use FileObject to store User cover_image
- `d316e39d` - chore: add migration 2d226d278d3b_add_column_user_cover_image.py
- `04d41e59` - chore: add migration 8b0da77a7479_add_column_user_photo_image.py
- `afad9d27` - add migration 10aea8b9a3b4_add_column_photo_carte_presse_image.py
- `f3f80181` - chore: add flask commands "dump_photos.py" "load_photos.py" for photo migration to s3
- `01125202` - wip use s3 for images
- `d3529b57` - chore: fix migration downgrade
- `8b67205d` - chore: fix migration downgrade

### KYC Views Adaptation
- `a0106174` - refactor: adapt dynform and kyc view to use FileObject, remove tmp blob
- `7192980b` - fix: kyc: FileObject creation in view, fix tests
- `15a884a9` - fix: kyc views, require better loading of images, serialization
- `31cc75fb` - fix: kyc views, better serialization, add file_object_utils.py
- `acec0fc4` - fix: kyc views, keep existing image if no new image upload done
- `71a57441` - fix: show photo image in profile
- `80e470f7` - fix: change format of fileObject/dict in KYC

### Tests and Refactoring
- `ff9cea14` - test: more unit tests (coverage now at 70%)
- `1d80aab0` - test: refact structure
- `6731c57c` - refact: fix several commit/flush issues, and fix tests
- `411ab556` - tests: quick fix tests by initializing Minio in conftest.py
- `99774200` - fix e2e tests on postgres
- `f20d93d5` - refact/tests: more "web" tests to "tests/c_e2e"
- `173e9c7d` - test/refactor: make e2e tests instead of using mocks
- `7573677c` - test: more tests
- `c32116ad` - add more tests
- `06e15863` - cleanup tests

### Miscellaneous Fixes
- `b0f47471` - fix: fix missing image (None value for photo)
- `871c3f67` - fix: class attributes bug
- `746fd3c7` - fix: class attribut bug in admin/pages/modif_users.py
- `56cfd727` - fix: bugs revealed by tests
- `2857d89c` - fix: typo in template
- `cb70f507` - chore: add deptry exceptions
