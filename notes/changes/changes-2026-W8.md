# Changes Week 8, 2026

## Wire Module - Major Refactoring

Complete code review and refactoring of `src/app/modules/wire/`.

### Signal Receivers Consolidation

Merged `article_receiver.py` and `communique_receiver.py` into single `receivers.py`:

- Shared helper `_update_post_common()` for common field updates
- Separate type-specific functions for article and communique handling
- Removed dead code assigning non-existent image attributes (`image_url`, `image_caption`, `image_copyright`)
- Reduced from 200 lines to 167 lines

### New Repositories

Added `repositories.py` with proper repository pattern:

```python
@service
class ArticlePostRepository(Repository[ArticlePost]):
    def get_by_newsroom_id(self, newsroom_id: int) -> ArticlePost | None

@service
class PressReleasePostRepository(Repository[PressReleasePost]):
    def get_by_newsroom_id(self, newsroom_id: int) -> PressReleasePost | None
```

Receivers now use repositories via `svcs.flask.container` instead of direct queries.

### ViewModel Consolidation

Created `PostVMMixin` base class for shared logic:

- `extra_attrs()` method shared between ArticleVM and PressReleaseVM
- `get_comments()` method with configurable `_comment_prefix`
- Fixed MRO: classes now inherit `(PostVMMixin, Wrapper)` for correct method resolution
- Reduced ~90 lines of duplicated code

### Bug Fixes

- Fixed `post.subheader` → `post.summary` (attribute didn't exist)
- Fixed comment `object_id` prefix for press releases: `"article:"` → `"press-release:"`
- Added `selectinload(Comment.owner)` to prevent N+1 queries

### Type Hints

Added comprehensive type annotations:

- `routing.py`: URL functions with `-> str`
- `wire.py`: View methods with `Response`, `FilterBar`, `Tab`, `Callable`
- `_filters.py`: All properties and methods
- `_tabs.py`: `get_tabs()`, `is_active`, `get_stmt()`, `get_authors()`

Fixed Liskov violation: `get_authors()` returns `Iterable[User] | None` consistently.

### Security Improvements

- Added `ALLOWED_FILTER_FIELDS` allowlist in `_tabs.py`
- Added filter ID validation against known filters in `_filters.py`
- Added logging for JSON decode failures in filter state

### Code Cleanup

- Removed redundant `elvis()` function
- Extracted `DEFAULT_POSTS_LIMIT = 30` constant
- Removed commented imports

## Events Module

- Fixed view count tracking
- Fixed comments functionality
- Fixed like button behavior

## Type Checking Migration

Adopted `ty` (pyrefly) as primary type checker instead of mypy.

### Cleanup

Removed 23 unnecessary `# type: ignore` comments across multiple files:

- `organisation.py`, `events/models.py`, `wire/models.py`
- `events_list.py`, `event_card.py`, `event_detail.py`
- `business_wall_registration.py`, `publications.py`
- `_table.py`, `avis_enquete.py`, `expert_selectors.py`

### Type Fixes

- Fixed `Mapped[dict]` → `Mapped[list]` in Organisation model (resolved 15+ errors)
- Added `ClassVar` to Table base class `columns` declaration
- Fixed SQLAlchemy query comparisons: `.where(Model.owner == user)` → `.where(Model.owner_id == user.id)`

## Business Wall

- Added tests for free BW creation
- Added `@service` decorator to BW services
- Created free BW using services with deferred commit
- Fixed BigInteger requirements for user.id and org.id in BW classes
- Added migrations for Integer → BigInteger conversions

## FileObject Migration

- Removed old blob-related code
- Moved everything to FileObject pattern

## Event Calendar

- Refactored event calendar
- Updated event data model
