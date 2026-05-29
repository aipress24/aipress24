# Changes Week 49, 2025

## User Photo Migration to S3

Following last week's article/communiqué/event migration, user photos move to S3-backed `FileObject`.

- New columns : `user.photo_image`, `user.cover_image`, `photo_carte_presse_image` (3 migrations).
- Flask commands `dump_photos` / `load_photos` to migrate existing photos.
- KYC dynforms refactored to use `FileObject` ; legacy `tmp blob` system dropped ; `file_object_utils.py` added for serialisation. Existing images preserved when no new upload.
- Fixes : `None` photo values, `FileObject/dict` format in KYC, class attribute bug in `admin/pages/modif_users.py`, profile photo display.

## Test Suite Improvements

- Test structure reorganised : "web" tests moved to `tests/c_e2e/` ; mock-based tests converted to real e2e.
- MinIO initialised in `conftest.py` ; PostgreSQL + SQLite test runs supported.
- Coverage **58 % → 70 %** (+12 pts). Numerous unit tests added, several commit/flush bugs surfaced.
