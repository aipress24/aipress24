# Changes Week 48, 2025

## Migration to S3 Storage for Images

Migrated image storage from the custom `BlobService` to S3-compatible storage via `advanced_alchemy`'s `FileObject`. Done incrementally over 3 days (Communiqué → Article → Event images), each with its own Alembic migration.

- S3 storage registered via `fsspec` in `flask/extensions.py` (configurable endpoint, credentials, bucket). Local storage option kept commented.
- `Image`, `ComImage`, `EventImage` models : `blob_id: str` → `content: FileObject` (`StoredObject(backend="s3")`).
- Dedicated `SQLAlchemySyncRepository` repositories : `ImageRepository`, `ComImageRepository`, `EventImageRepository`.
- CRUD : uploads now build a `FileObject` (bytes + filename + content_type) and call `.save()` ; retrieval uses `stored_file.get_content()` + `BytesIO` ; deletion via `image.content.delete()`. `BlobService` / `svcs.flask.container` dependency dropped.
- UI : `object-cover` → `object-contain` in carousel + image editors to stop cropping.

Side fixes : double `read()` in event `_add_image`, image positioning on move up/down, deletion of stored images, migration script `cb2670cb8cbe`, fallback blank image when not found.
