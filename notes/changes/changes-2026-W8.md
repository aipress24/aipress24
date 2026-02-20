# Changes Week 8, 2026

## Wire Module - Major Refactoring

Complete code review and refactoring of `src/app/modules/wire/`.

### Signal Receivers Consolidation

Merged `article_receiver.py` and `communique_receiver.py` into single `receivers.py`:

- Shared helper `_update_post_common()` for common field updates
- Separate type-specific functions for article and communique handling
- Removed dead code assigning non-existent image attributes (`image_url`, `image_caption`, `image_copyright`)
- Consistent naming: `on_article_published`, `on_communique_published`, etc.
- Uses direct SQLAlchemy queries for simplicity

### Critical Bug Fixes

1. **Empty author filter bug** (`_tabs.py:65`):
   - `WallTab.get_authors()` returns `[]`
   - Check `if authors is not None` was True for `[]`, causing `owner_id.in_([])` which matched nothing
   - Fixed: Changed to `if authors:` so empty list means "no filter"

2. **Invalid `published_at` dates** (`receivers.py`):
   - Communiqués with placeholder dates like `1111-11-11` were copied to Wire posts
   - Posts with ancient dates sorted to bottom and didn't appear
   - Fixed: If source date year < 2000, use `now()` instead

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

Added comprehensive type annotations.

### Security Improvements

- Added `ALLOWED_FILTER_FIELDS` allowlist in `_tabs.py`
- Added filter ID validation against known filters in `_filters.py`
- Added logging for JSON decode failures in filter state

### Code Cleanup

- Removed redundant `elvis()` function
- Extracted `DEFAULT_POSTS_LIMIT = 30` constant
- Removed commented imports

## Swork Module - Code Review and Fixes

Complete code review of `src/app/modules/swork/`. See `local-notes/swork-code-review.md` for full report.

### High Priority Fixes

1. **Input validation in group creation** (`views/group_new.py`):
   - Added `form.get()` with `.strip()` instead of direct access
   - Added validation for empty group name
   - Added flash messages for success/error feedback

2. **Null safety for profile access** (`views/_common.py`):
   - Added null check for `user.profile` and `target_user.profile` before attribute access
   - Prevents AttributeError when profiles are incomplete

3. **N+1 query prevention** (`views/_common.py`):
   - Added `selectinload()` for `ArticlePost.owner` and `ArticlePost.publisher`
   - Converted from `.query()` to `select()` pattern

4. **Accurate filter counts** (`components/members_list.py`, `components/organisations_list.py`):
   - Count now uses `len(results)` after filtering
   - Previously count query ignored applied filters

### Medium Priority Fixes

5. **Type hints** (`components/base.py`, `routes.py`):
   - Added `-> str` to `url_for_group`
   - Added `Select` type hints to `apply_search`, `apply_filters`
   - Added proper types to `Filter.apply`, `Filter.active_options`
   - Used `@abstractmethod` for `search_clause`

6. **Filter improvements** (`components/organisations_list.py`):
   - Added type hints to all filter methods
   - Fixed ClassVar type annotations

7. **Dead code removal** (`components/__init__.py`):
   - Removed all commented-out component registrations
   - Added docstring explaining auto-registration via `@register`

8. **SQLAlchemy modernization** (`views/organisation.py`):
   - Converted `db.session.query(User).filter(...)` to `select(User).where(...)`
   - Cleaned up imports: `import abc` → `from abc import ABC, abstractmethod`

## N+1 Query Detector - New Infrastructure

Added `src/app/flask/lib/n_plus_one_detector.py`:

### Features

- Hooks into SQLAlchemy's `before_cursor_execute` event
- Tracks all queries during a request
- Normalizes queries by replacing literals with placeholders
- Detects repeated query patterns (threshold configurable)
- Generates detailed reports with query counts and sample parameters

### Configuration

```python
N_PLUS_ONE_ENABLED: bool | None = None  # None = use debug mode
N_PLUS_ONE_THRESHOLD: int = 3           # Min repeated queries to trigger
N_PLUS_ONE_LOG_LEVEL: str = "WARNING"   # Log level for alerts
N_PLUS_ONE_RAISE: bool = False          # Raise exception instead of logging
```

### Usage

```python
from app.flask.lib.n_plus_one_detector import init_n_plus_one_detector

def create_app():
    app = Flask(__name__)
    init_n_plus_one_detector(app)
    return app
```

### Helper Functions

- `get_query_count()` - Get total queries in current request
- `get_query_stats()` - Get detailed query statistics

Includes 20 unit tests covering normalization, tracking, and detection.

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
- `social_graph/_adapters.py` (removed 2 unused type ignores)

### Type Fixes

- Fixed `Mapped[dict]` → `Mapped[list]` in Organisation model (resolved 15+ errors)
- Added `ClassVar` to Table base class `columns` declaration
- Fixed SQLAlchemy query comparisons: `.where(Model.owner == user)` → `.where(Model.owner_id == user.id)`
- Added `# type: ignore[assignment]` for SQLAlchemy descriptor assignments in faker scripts

## Business Wall - Major Development

### Activation Flow

- Reorganized step numbering in Python files and templates
- Swapped steps 1 and 2 (invitations before members list)
- Added "not authorized" page for various error situations
- Redirect to "not_authorized" page when appropriate

### Organisation Membership

- Page B01: Manage organisation members (remove members from BW)
- Page B02: Invite organisation members
- BW owner automatically becomes member of the Organisation
- BW owner cannot remove themselves from the BW organisation
- Helper functions: `invite_user_role()`, `revoke_user_role()`, `invite_bwmi_by_email()`, `revoke_bwmi_by_email()`

### Role Management

- Stage B03: Manager lists with POST management for BWMI and BWPRI
- Stage 4 displays BW owner from role_assignments
- Added `bw_managers_ids()` function returning BW managers user IDs

### Dashboard Updates

- Management of organisation members and invitations
- Updated chapter numbers
- Display `bw_info.rate_message` for "GRATUIT"/"PAYANT"
- WIP menu redirects to `bw.index` page (was dashboard)

### Payer Information

- Added fields for payer information (when different from owner)
- Added `payer_is_owner` field to BusinessWall table
- Added FK for BusinessWall to User table for `owner_id` and `payer_id`
- Added FK for BusinessWall to Organisation table
- Collect payer information from BW form

### Bug Fixes

- Organisation can have only one BW (fixed broken test DB case)
- Remove reset link from BW forms
- Fixed broken link in `bw_activation/dashboard.html`
- Create minimal Organisation for user if none exists at BW creation
- Added missing value in businesswall config.py

### Database Migrations

- Integer → BigInteger in BusinessWall table
- Added `payer_is_owner` field
- Added fields and foreign keys for BusinessWall

### Tests

- Added tests for free BW creation
- Added `@service` decorator to BW services
- Created free BW using services with deferred commit

## FileObject Migration

- Removed old blob-related code
- Moved everything to FileObject pattern

## Event Calendar

- Refactored event calendar
- Updated event data model
