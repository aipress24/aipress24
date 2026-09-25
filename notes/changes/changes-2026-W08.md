# Changes Week 8, 2026

## Wire Module — Code Review + Refactor

Full review and consolidation of `src/app/modules/wire/`.

- Signal receivers : `article_receiver.py` + `communique_receiver.py` merged into `receivers.py`. Shared `_update_post_common()` helper, type-specific functions, dead code removed (non-existent `image_url`, `image_caption`, `image_copyright`), consistent naming.
- **Bug — empty author filter** (`_tabs.py:65`) : `WallTab.get_authors()` returns `[]`, but `if authors is not None` was True, causing `owner_id.in_([])` to match nothing. Fixed to `if authors:`.
- **Bug — invalid `published_at`** : communiqués with placeholder dates (`1111-11-11`) sorted to the bottom and disappeared. Fix : if source year < 2000, use `now()`.
- ViewModel consolidation : new `PostVMMixin` base with shared `extra_attrs()` and `get_comments()` (configurable `_comment_prefix`). MRO corrected. ~90 lines of duplication removed.
- Fixes : `post.subheader` → `post.summary` ; comment `object_id` prefix `"article:"` → `"press-release:"` for press releases ; `selectinload(Comment.owner)` to avoid N+1.
- Security : `ALLOWED_FILTER_FIELDS` allowlist in `_tabs.py` ; filter-ID validation in `_filters.py` ; JSON decode failures logged.
- Cleanup : `elvis()` removed, `DEFAULT_POSTS_LIMIT = 30` constant, comprehensive type annotations.

## Swork Module — Code Review

Full review of `src/app/modules/swork/`. Detailed report in `local-notes/swork-code-review.md`.

- **Input validation** (`group_new.py`) : `form.get()` + `.strip()` ; empty-name check ; flash messages.
- **Null safety** (`_common.py`) : null check on `user.profile` / `target_user.profile` to prevent AttributeError.
- **N+1 prevention** (`_common.py`) : `selectinload` for `ArticlePost.owner` / `.publisher` ; converted to SQLAlchemy 2.0 `select()` pattern.
- **Accurate filter counts** (members / organisations lists) : `len(results)` *after* filtering, not the pre-filter query.
- Type hints + abstract methods cleanup on `BaseList`, `Filter`, selectors.
- Dead code removal (commented component registrations) ; `db.session.query()` → `select().where()` in `organisation.py`.

## N+1 Query Detector — New Infrastructure

New module `app/flask/lib/n_plus_one_detector.py` that hooks SQLAlchemy's `before_cursor_execute` to track queries per request, normalise them (literals → placeholders), and detect repeats above a configurable threshold.

- Config : `N_PLUS_ONE_ENABLED`, `N_PLUS_ONE_THRESHOLD=3`, `N_PLUS_ONE_LOG_LEVEL`, `N_PLUS_ONE_RAISE`.
- Helpers : `get_query_count()`, `get_query_stats()`.
- 20 unit tests.

## Events Module

View-count tracking, comments, and like button : fixes.

## Type Checking — Migration to `ty` (pyrefly)

- Adopted `ty` as primary type checker (instead of mypy).
- 23 unnecessary `# type: ignore` comments removed.
- `Mapped[dict]` → `Mapped[list]` in Organisation (resolved 15+ errors).
- `ClassVar` added to Table base class `columns`.
- Query comparisons : `.where(Model.owner == user)` → `.where(Model.owner_id == user.id)`.

## Business Wall — Major Development

Activation flow :

- Step numbering reorganised ; steps 1 and 2 swapped (invitations before members list).
- New "not authorized" page for various error situations.

Organisation membership :

- B01 page : manage organisation members (remove from BW).
- B02 page : invite organisation members.
- BW owner becomes a member automatically and cannot remove themselves.
- Helpers : `invite_user_role`, `revoke_user_role`, `invite_bwmi_by_email`, `revoke_bwmi_by_email`.

Role management :

- Stage B03 : manager lists with POST management for BWMI / BWPRI.
- Stage 4 displays the BW owner from `role_assignments`.
- New `bw_managers_ids()` helper.

Dashboard + payer info :

- Display `bw_info.rate_message` ("GRATUIT" / "PAYANT"). WIP menu now redirects to `bw.index` (was the dashboard).
- Payer fields when payer ≠ owner ; new `payer_is_owner` column ; FKs from `BusinessWall` to `User` (owner / payer) and `Organisation`. Form collects payer information.

Fixes : an Organisation may only have one BW (broken test DB case) ; reset link removed from BW forms ; broken link in `dashboard.html` fixed ; minimal Organisation auto-created for user without one at BW creation.

DB migrations : Integer → BigInteger ; `payer_is_owner` ; BW FKs.

## Misc

- `FileObject` migration : old blob-related code removed.
- Event calendar refactored ; event data model updated.
