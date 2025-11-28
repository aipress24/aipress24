# Changes Week 48, 2025

## Migration to S3 Storage for Images

This set of changes migrates the image storage system from a custom `BlobService` to **S3-compatible storage** using `advanced_alchemy`'s `FileObject` system.

### Key Changes

**1. Storage Backend Configuration** (`src/app/flask/extensions.py`)
- Added S3 storage registration using `fsspec` filesystem with configurable endpoint, credentials, and bucket
- Local storage option available but commented out

**2. Model Changes** (Article, Communique, Event images)
- Replaced `blob_id: str` column with `content: FileObject` using `StoredObject(backend="s3")`
- Affects: `Image`, `ComImage`, `EventImage` models

**3. Repository Layer**
- Added dedicated repositories: `ImageRepository`, `ComImageRepository`, `EventImageRepository`
- Using `SQLAlchemySyncRepository` from advanced_alchemy

**4. CRUD Operations** (`articles.py`, `communiques.py`, `events.py`)
- **Upload**: Now creates `FileObject` with content bytes, filename, and content_type, then calls `.save()`
- **Retrieval**: Uses `stored_file.get_content()` returning bytes via `BytesIO` instead of file paths
- **Deletion**: Calls `image.content.delete()` to remove files from S3
- Removed dependency on `BlobService` and `svcs.flask.container`

**5. UI Fixes**
- Changed `object-cover` to `object-contain` in carousel and image editors to prevent cropping

### Commit Progression

The migration was done incrementally across 3 days:

1. Communique images -> Article images -> Event images
2. Each with corresponding database migrations
3. Several bug fixes for deletion, double reads, and image positioning

### Commits

- `f2eb713` - fix: fix moving up/down images and image position
- `83d483e` - fix: fix deletion of stored images
- `cba6701` - fix: fix double read() in event _add_image
- `567c26e` - fix: fix migration cb2670cb8cbe_use_s3_for_article_image.py
- `d06ab5b` - add migration f41e8fa6e55b_use_s3_for_event_image.py
- `715b125` - chore: use advanced_alchemy FileObject to store Event images
- `048afdf` - fix: do not crop images in the image editor for article/communique/event
- `6481962` - fix: send blank image if image not found for article, communique
- `650281d` - chore: add migration cb2670cb8cbe_use_s3_for_article_image.py
- `85fa491` - chore: use advanced_alchemy FileObject to store Article images
- `2f70571` - fix: images in carousel are no more truncated
- `2e33c81` - doc: add notes/Install_S3_MinIO_MacOS.md
- `6a29e40` - chore: configure S3 storage (using local MinIO for tests)
- `8999024` - chore: add migrations for FileObject column in Communique Image
- `a4902ce` - chore: use advanced_alchemy FileObject to store Communique images
