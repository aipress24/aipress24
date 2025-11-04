# Advanced Alchemy

## About

A carefully crafted, thoroughly tested, optimized companion library for SQLAlchemy,
offering:

- Sync and async repositories, featuring common CRUD and highly optimized bulk operations
- Integration with major web frameworks including Litestar, Starlette, FastAPI, Sanic
- Custom-built alembic configuration and CLI with optional framework integration
- Utility base classes with audit columns, primary keys and utility functions
- Built in `File Object` data type for storing objects:
    - Unified interface for various storage backends ([`fsspec`](https://filesystem-spec.readthedocs.io/en/latest/) and [`obstore`](https://developmentseed.org/obstore/latest/))
    - Optional lifecycle event hooks integrated with SQLAlchemy's event system to automatically save and delete files as records are inserted, updated, or deleted.
- Optimized JSON types including a custom JSON type for Oracle
- Integrated support for UUID6 and UUID7 using [`uuid-utils`](https://github.com/aminalaee/uuid-utils) (install with the `uuid` extra)
- Integrated support for Nano ID using [`fastnanoid`](https://github.com/oliverlambson/fastnanoid) (install with the `nanoid` extra)
- Custom encrypted text type with multiple backend support including [`pgcrypto`](https://www.postgresql.org/docs/current/pgcrypto.html) for PostgreSQL and the Fernet implementation from [`cryptography`](https://cryptography.io/en/latest/) for other databases
- Custom password hashing type with multiple backend support including [`Argon2`](https://github.com/P-H-C/phc-winner-argon2), [`Passlib`](https://passlib.readthedocs.io/en/stable/), and [`Pwdlib`](https://pwdlib.readthedocs.io/en/stable/) with automatic salt generation
- Pre-configured base classes with audit columns UUID or Big Integer primary keys and
  a [sentinel column](https://docs.sqlalchemy.org/en/20/core/connections.html#configuring-sentinel-columns).
- Synchronous and asynchronous repositories featuring:
    - Common CRUD operations for SQLAlchemy models
    - Bulk inserts, updates, upserts, and deletes with dialect-specific enhancements
    - Integrated counts, pagination, sorting, filtering with `LIKE`, `IN`, and dates before and/or after.
- Tested support for multiple database backends including:
    - SQLite via [aiosqlite](https://aiosqlite.omnilib.dev/en/stable/) or [sqlite](https://docs.python.org/3/library/sqlite3.html)
    - Postgres via [asyncpg](https://magicstack.github.io/asyncpg/current/) or [psycopg3 (async or sync)](https://www.psycopg.org/psycopg3/)
    - MySQL via [asyncmy](https://github.com/long2ice/asyncmy)
    - Oracle via [oracledb (async or sync)](https://oracle.github.io/python-oracledb/) (tested on 18c and 23c)
    - Google Spanner via [spanner-sqlalchemy](https://github.com/googleapis/python-spanner-sqlalchemy/)
    - DuckDB via [duckdb_engine](https://github.com/Mause/duckdb_engine)
    - Microsoft SQL Server via [pyodbc](https://github.com/mkleehammer/pyodbc) or [aioodbc](https://github.com/aio-libs/aioodbc)
    - CockroachDB via [sqlalchemy-cockroachdb (async or sync)](https://github.com/cockroachdb/sqlalchemy-cockroachdb)
- ...and much more

## Usage


### Repositories

Advanced Alchemy includes a set of asynchronous and synchronous repository classes for easy CRUD
operations on your SQLAlchemy models.


```python
from advanced_alchemy import base, repository, config
from sqlalchemy import create_engine
from sqlalchemy.orm import Mapped, sessionmaker


class User(base.UUIDBase):
    # you can optionally override the generated table name by manually setting it.
    __tablename__ = "user_account"  # type: ignore[assignment]
    email: Mapped[str]
    name: Mapped[str]


class UserRepository(repository.SQLAlchemySyncRepository[User]):
    """User repository."""

    model_type = User


db = config.SQLAlchemySyncConfig(connection_string="duckdb:///:memory:", session_config=config.SyncSessionConfig(expire_on_commit=False))

# Initializes the database.
with db.get_engine().begin() as conn:
    User.metadata.create_all(conn)

with db.get_session() as db_session:
    repo = UserRepository(session=db_session)
    # 1) Create multiple users with `add_many`
    bulk_users = [
        {"email": 'cody@litestar.dev', 'name': 'Cody'},
        {"email": 'janek@litestar.dev', 'name': 'Janek'},
        {"email": 'peter@litestar.dev', 'name': 'Peter'},
        {"email": 'jacob@litestar.dev', 'name': 'Jacob'}
    ]
    objs = repo.add_many([User(**raw_user) for raw_user in bulk_users])
    db_session.commit()
    print(f"Created {len(objs)} new objects.")

    # 2) Select paginated data and total row count.  Pass additional filters as kwargs
    created_objs, total_objs = repo.list_and_count(LimitOffset(limit=10, offset=0), name="Cody")
    print(f"Selected {len(created_objs)} records out of a total of {total_objs}.")

    # 3) Let's remove the batch of records selected.
    deleted_objs = repo.delete_many([new_obj.id for new_obj in created_objs])
    print(f"Removed {len(deleted_objs)} records out of a total of {total_objs}.")

    # 4) Let's count the remaining rows
    remaining_count = repo.count()
    print(f"Found {remaining_count} remaining records after delete.")
```


### Services

Advanced Alchemy includes an additional service class to make working with a repository easier.
This class is designed to accept data as a dictionary or SQLAlchemy model,
and it will handle the type conversions for you.

```python
from advanced_alchemy import base, repository, filters, service, config
from sqlalchemy import create_engine
from sqlalchemy.orm import Mapped, sessionmaker


class User(base.UUIDBase):
    # you can optionally override the generated table name by manually setting it.
    __tablename__ = "user_account"  # type: ignore[assignment]
    email: Mapped[str]
    name: Mapped[str]

class UserService(service.SQLAlchemySyncRepositoryService[User]):
    """User repository."""
    class Repo(repository.SQLAlchemySyncRepository[User]):
        """User repository."""

        model_type = User

    repository_type = Repo

db = config.SQLAlchemySyncConfig(connection_string="duckdb:///:memory:", session_config=config.SyncSessionConfig(expire_on_commit=False))

# Initializes the database.
with db.get_engine().begin() as conn:
    User.metadata.create_all(conn)

with db.get_session() as db_session:
    service = UserService(session=db_session)
    # 1) Create multiple users with `add_many`
    objs = service.create_many([
        {"email": 'cody@litestar.dev', 'name': 'Cody'},
        {"email": 'janek@litestar.dev', 'name': 'Janek'},
        {"email": 'peter@litestar.dev', 'name': 'Peter'},
        {"email": 'jacob@litestar.dev', 'name': 'Jacob'}
    ])
    print(objs)
    print(f"Created {len(objs)} new objects.")

    # 2) Select paginated data and total row count.  Pass additional filters as kwargs
    created_objs, total_objs = service.list_and_count(LimitOffset(limit=10, offset=0), name="Cody")
    print(f"Selected {len(created_objs)} records out of a total of {total_objs}.")

    # 3) Let's remove the batch of records selected.
    deleted_objs = service.delete_many([new_obj.id for new_obj in created_objs])
    print(f"Removed {len(deleted_objs)} records out of a total of {total_objs}.")

    # 4) Let's count the remaining rows
    remaining_count = service.count()
    print(f"Found {remaining_count} remaining records after delete.")
```

### Web Frameworks

Advanced Alchemy works with nearly all Python web frameworks.

#### Flask

```python
from flask import Flask
from advanced_alchemy.extensions.flask import AdvancedAlchemy, SQLAlchemySyncConfig

app = Flask(__name__)
alchemy = AdvancedAlchemy(
    config=SQLAlchemySyncConfig(connection_string="duckdb:///:memory:"), app=app,
)
```

For a full Flask example:

```python
from __future__ import annotations

import datetime  # noqa: TC003
import os
from uuid import UUID  # noqa: TC003

from flask import Flask, request
from msgspec import Struct
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from advanced_alchemy.extensions.flask import (
    AdvancedAlchemy,
    FlaskServiceMixin,
    SQLAlchemySyncConfig,
    base,
    filters,
    repository,
    service,
)


class Author(base.UUIDBase):
    """Author model."""

    name: Mapped[str]
    dob: Mapped[datetime.date | None]
    books: Mapped[list[Book]] = relationship(back_populates="author", lazy="noload")


class Book(base.UUIDAuditBase):
    """Book model."""

    title: Mapped[str]
    author_id: Mapped[UUID] = mapped_column(ForeignKey("author.id"))
    author: Mapped[Author] = relationship(lazy="joined", innerjoin=True, viewonly=True)


class AuthorService(service.SQLAlchemySyncRepositoryService[Author], FlaskServiceMixin):
    """Author service."""

    class Repo(repository.SQLAlchemySyncRepository[Author]):
        """Author repository."""

        model_type = Author

    repository_type = Repo


class AuthorSchema(Struct):
    """Author schema."""

    name: str
    id: UUID | None = None
    dob: datetime.date | None = None


app = Flask(__name__)
alchemy_config = SQLAlchemySyncConfig(connection_string="sqlite:///local.db", commit_mode="autocommit", create_all=True)
alchemy = AdvancedAlchemy(alchemy_config, app)


@app.route("/authors", methods=["GET"])
def list_authors():
    """List authors with pagination."""
    page, page_size = request.args.get("currentPage", 1, type=int), request.args.get("pageSize", 10, type=int)
    limit_offset = filters.LimitOffset(limit=page_size, offset=page_size * (page - 1))
    service = AuthorService(session=alchemy.get_sync_session())
    results, total = service.list_and_count(limit_offset)
    response = service.to_schema(results, total, filters=[limit_offset], schema_type=AuthorSchema)
    return service.jsonify(response)


@app.route("/authors", methods=["POST"])
def create_author():
    """Create a new author."""
    service = AuthorService(session=alchemy.get_sync_session())
    obj = service.create(**request.get_json())
    return service.jsonify(obj)


@app.route("/authors/<uuid:author_id>", methods=["GET"])
def get_author(author_id: UUID):
    """Get an existing author."""
    service = AuthorService(session=alchemy.get_sync_session(), load=[Author.books])
    obj = service.get(author_id)
    return service.jsonify(obj)


@app.route("/authors/<uuid:author_id>", methods=["PATCH"])
def update_author(author_id: UUID):
    """Update an author."""
    service = AuthorService(session=alchemy.get_sync_session(), load=[Author.books])
    obj = service.update(**request.get_json(), item_id=author_id)
    return service.jsonify(obj)


@app.route("/authors/<uuid:author_id>", methods=["DELETE"])
def delete_author(author_id: UUID):
    """Delete an author."""
    service = AuthorService(session=alchemy.get_sync_session())
    service.delete(author_id)
    return "", 204


if __name__ == "__main__":
    app.run(debug=os.environ["ENV"] == "dev")

```

# Modeling

Advanced Alchemy enhances SQLAlchemy\'s modeling capabilities with
production-ready base classes, mixins, and specialized types. This guide
demonstrates modeling for a blog system with posts and tags, showcasing
key features and best practices.

## Base Classes

Advanced Alchemy provides several base classes optimized for different
use cases. Any model can utilize these pre-defined declarative bases
from sqlchemy. Here\'s a brief overview of the included classes:

  ------------------------------------------------------------------------------
  Base Class            Features
  --------------------- --------------------------------------------------------
  `BigIntBase`          BIGINT primary keys for tables

  `BigIntAuditBase`     BIGINT primary keys for tables, Automatic
                        created_at/updated_at timestamps

  `IdentityBase`        Primary keys using database IDENTITY feature instead of
                        sequences

  `IdentityAuditBase`   Primary keys using database IDENTITY feature, Automatic
                        created_at/updated_at timestamps

  `UUIDBase`            UUID primary keys

  `UUIDv6Base`          UUIDv6 primary keys

  `UUIDv7Base`          UUIDv7 primary keys

  `UUIDAuditBase`       UUID primary keys, Automatic created_at/updated_at
                        timestamps

  `UUIDv6AuditBase`     UUIDv6 primary keys, Automatic created_at/updated_at
                        timestamps

  `UUIDv7AuditBase`     Time-sortable UUIDv7 primary keys, Automatic
                        created_at/updated_at timestamps

  `NanoIDBase`          URL-friendly unique identifiers, Shorter than UUIDs,
                        collision resistant

  `NanoIDAuditBase`     URL-friendly IDs with audit timestamps, Combines Nanoid
                        benefits with audit trails
  ------------------------------------------------------------------------------

  : Base Classes and Features

## Mixins

Additionally, Advanced Alchemy provides mixins to enhance model
functionality:

+----------------------+--------------------------------------------------------+
| Mixin                | Features                                               |
+======================+========================================================+
| `SlugKey`            | | Adds URL-friendly slug field                         |
+----------------------+--------------------------------------------------------+
| `AuditColumns`       | | Automatic created_at/updated_at timestamps           |
|                      | | Tracks record modifications                          |
|                      | | `updated_at` refreshes during flush when any mapped  |
|                      |   column value changes, while preserving explicit      |
|                      |   timestamp overrides                                  |
+----------------------+--------------------------------------------------------+
| `BigIntPrimaryKey`   | | Adds BigInt primary key with sequence                |
+----------------------+--------------------------------------------------------+
| `IdentityPrimaryKey` | | Adds primary key using database IDENTITY feature     |
+----------------------+--------------------------------------------------------+
| `UniqueMixin`        | | Automatic Select or Create for many-to-many          |
|                      |   relationships                                        |
+----------------------+--------------------------------------------------------+

: Available Mixins

## Basic Model Example

Let\'s start with a simple blog post model:

```python
import datetime
from typing import Optional

from advanced_alchemy.base import BigIntAuditBase
from sqlalchemy.orm import Mapped, mapped_column

class Post(BigIntAuditBase):
    """Blog post model with auto-incrementing ID and audit fields.

    Attributes:
        title: The post title
        content: The post content
        published: Publication status
        published_at: Timestamp of publication
        created_at: Timestamp of creation (from BigIntAuditBase)
        updated_at: Timestamp of last update (from BigIntAuditBase)
    """

    title: Mapped[str] = mapped_column(index=True)
    content: Mapped[str]
    published: Mapped[bool] = mapped_column(default=False)
    published_at: Mapped[Optional[datetime.datetime]] = mapped_column(default=None)
```

## Many-to-Many Relationships {#many_to_many_relationships}

Let\'s implement a tagging system using a many-to-many relationship.
This example demonstrates: - Association table configuration -
Relationship configuration with lazy loading - Slug key mixin - Index
creation

```python
from __future__ import annotations
from sqlalchemy import Column, ForeignKey, Table
from sqlalchemy.orm import relationship
from sqlalchemy.orm import Mapped, mapped_column
from advanced_alchemy.base import BigIntAuditBase, orm_registry, SlugKey
from typing import List

# Association table for post-tag relationship
post_tag = Table(
    "post_tag",
    orm_registry.metadata,
    Column("post_id", ForeignKey("post.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tag.id", ondelete="CASCADE"), primary_key=True)
)

class Post(BigIntAuditBase):

    title: Mapped[str] = mapped_column(index=True)
    content: Mapped[str]
    published: Mapped[bool] = mapped_column(default=False)

    # Many-to-many relationship with tags
    tags: Mapped[List["Tag"]] = relationship(
        secondary=post_tag,
        back_populates="posts",
        lazy="selectin"
    )

class Tag(BigIntAuditBase, SlugKey):
    """Tag model with automatic slug generation.

    The SlugKey mixin automatically adds a slug field to the model.
    """

    name: Mapped[str] = mapped_column(unique=True, index=True)
    posts: Mapped[List[Post]] = relationship(
        secondary=post_tag,
        back_populates="tags",
        viewonly=True
    )
```

If we want to interact with the models above, we might use something
like the following:

```python
from sqlalchemy.ext.asyncio import AsyncSession
from advanced_alchemy.utils.text import slugify

async def add_tags_to_post(
    db_session: AsyncSession,
    post: Post,
    tag_names: list[str]
) -> Post:
    """Add tags to a post, looking up existing tags and creating new ones if needed."""
    existing_tags = await db_session.scalars(
        select(Tag).filter(Tag.slug.in_([slugify(name) for name in tag_names]))
    )
    new_tags = [Tag(name=name, slug=slugify(name)) for name in tag_names if name not in {tag.name for tag in existing_tags}]
    post.tags.extend(new_tags + list(existing_tags))
    db_session.merge(post)
    await db_session.flush()
    return post
```

Fortunately, we can remove some of this logic thanks to
`UniqueMixin`{.interpreted-text role="class"}.

## Using `UniqueMixin`{.interpreted-text role="class"} {#using_unique_mixin}

`UniqueMixin`{.interpreted-text role="class"} provides automatic
handling of unique constraints and merging of duplicate records. When
using the mixin, you must implement two classmethods:
`unique_hash <UniqueMixin.unique_hash>`{.interpreted-text role="meth"}
and `unique_filter <UniqueMixin.unique_hash>`{.interpreted-text
role="meth"}. These methods enable:

- Automatic lookup of existing records
- Safe merging of duplicates
- Atomic get-or-create operations
- Configurable uniqueness criteria

Let\'s enhance our Tag model with `UniqueMixin`{.interpreted-text
role="class"}:

```python
from advanced_alchemy.base import BigIntAuditBase, SlugKey
from advanced_alchemy.mixins import UniqueMixin
from advanced_alchemy.utils.text import slugify
from sqlalchemy.sql.elements import ColumnElement
from typing import Hashable

class Tag(BigIntAuditBase, SlugKey, UniqueMixin):
    """Tag model with unique name constraint and automatic slug generation.

    The UniqueMixin provides:
    - Automatic lookup of existing records
    - Safe merging of duplicates
    - Consistent slug generation
    """

    name: Mapped[str] = mapped_column(unique=True, index=True)
    posts: Mapped[list[Post]] = relationship(
        secondary=post_tag,
        back_populates="tags",
        viewonly=True
    )

    @classmethod
    def unique_hash(cls, name: str, slug: str | None = None) -> Hashable:
        """Generate a unique hash for deduplication."""
        return slugify(name)

    @classmethod
    def unique_filter(
        cls,
        name: str,
        slug: str | None = None,
    ) -> ColumnElement[bool]:
        """SQL filter for finding existing records."""
        return cls.slug == slugify(name)
```

We can now take advantage of
`UniqueMixin.as_unique_async`{.interpreted-text role="meth"} to simplify
the logic.

```python
from sqlalchemy.ext.asyncio import AsyncSession
from advanced_alchemy.utils.text import slugify

async def add_tags_to_post(
    db_session: AsyncSession,
    post: Post,
    tag_names: list[str]
) -> Post:
    """Add tags to a post, creating new tags if needed."""
    # The UniqueMixin automatically handles:
    # 1. Looking up existing tags
    # 2. Creating new tags if needed
    # 3. Merging duplicates
    post.tags = [
      await Tag.as_unique_async(db_session, name=tag_text, slug=slugify(tag_text))
      for tag_text in tag_names
    ]
    db_session.merge(post)
    await db_session.flush()
    return post
```

## Customizing Declarative Base

In case one of the built in declarative bases do not meet your needs (or
you already have your own), Advanced Alchemy already supports
customizing the `DeclarativeBase` class.

Here\'s an example showing a class to generate a server-side UUID
primary key for \`postgres\`:

```python
import datetime
from uuid import UUID, uuid4

from advanced_alchemy.base import CommonTableAttributes, orm_registry
from sqlalchemy import text
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    declared_attr,
    mapped_column,
    orm_insert_sentinel,
)


class ServerSideUUIDPrimaryKey:
    """UUID Primary Key Field Mixin."""

    id: Mapped[UUID] = mapped_column(default=uuid4, primary_key=True, server_default=text("gen_random_uuid()"))
    """UUID Primary key column."""

    # noinspection PyMethodParameters
    @declared_attr
    def _sentinel(cls) -> Mapped[int]:
        """Sentinel value required for SQLAlchemy bulk DML with UUIDs."""
        return orm_insert_sentinel(name="sa_orm_sentinel")


class ServerSideUUIDBase(ServerSideUUIDPrimaryKey, CommonTableAttributes, DeclarativeBase):
    """Base for all SQLAlchemy declarative models with the custom UUID primary key ."""

    registry = orm_registry


# Using ServerSideUUIDBase
class User(ServerSideUUIDBase):
    """User model with ServerSideUUIDBase."""

    username: Mapped[str] = mapped_column(unique=True, index=True)
    email: Mapped[str] = mapped_column(unique=True)
    full_name: Mapped[str]
    is_active: Mapped[bool] = mapped_column(default=True)
    last_login: Mapped[datetime.datetime | None] = mapped_column(default=None)
```

With this foundation in place, let\'s look at the repository pattern.

# Repositories

Advanced Alchemy\'s repository pattern provides a clean, consistent
interface for database operations. This pattern abstracts away the
complexity of SQLAlchemy sessions and query-building while providing
type-safe operations.

## Understanding Repositories

A repository acts as a collection-like interface to your database
models, providing:

- Type-safe CRUD operations
- Filtering and pagination
- Bulk operations
- Transaction management
- Specialized repository types for common patterns

## Base Repository Types

+----------------------------------+-------------------------------------------------+
| Repository Class                 | Features                                        |
+==================================+=================================================+
| `SQLAlchemyAsyncRepository`      | | - Async session support                       |
|                                  | | - Basic CRUD operations                       |
|                                  | | - Filtering and pagination                    |
|                                  | | - Bulk operations                             |
+----------------------------------+-------------------------------------------------+
| `SQLAlchemyAsyncSlugRepository`  | | - Async session support                       |
|                                  | | - All base repository features                |
|                                  | | - Slug-based lookups                          |
|                                  | | - URL-friendly operations                     |
+----------------------------------+-------------------------------------------------+
| `SQLAlchemyAsyncQueryRepository` | | - Async session support                       |
|                                  | | - Custom query execution                      |
|                                  | | - Complex aggregations                        |
|                                  | | - Raw SQL support                             |
+----------------------------------+-------------------------------------------------+
| `SQLAlchemySyncRepository`       | | - Sync session support                        |
|                                  | | - Basic CRUD operations                       |
|                                  | | - Filtering and pagination                    |
|                                  | | - Bulk operations                             |
+----------------------------------+-------------------------------------------------+
| `SQLAlchemySyncSlugRepository`   | | - Sync session support                        |
|                                  | | - All base repository features                |
|                                  | | - Slug-based lookups                          |
|                                  | | - URL-friendly operations                     |
+----------------------------------+-------------------------------------------------+
| `SQLAlchemySyncQueryRepository`  | | - Sync session support                        |
|                                  | | - Custom query execution                      |
|                                  | | - Complex aggregations                        |
|                                  | | - Raw SQL support                             |
+----------------------------------+-------------------------------------------------+

: Repository Types

## Basic Repository Usage

:::: note
::: title
Note
:::

The following examples assumes the existence of the `Post` model defined
in `many_to_many_relationships`{.interpreted-text role="ref"} and the
`Tag` model defined in `using_unique_mixin`{.interpreted-text
role="ref"}.
::::

Let\'s implement a basic repository for our blog post model:

```python
from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

class PostRepository(SQLAlchemyAsyncRepository[Post]):
    """Repository for managing blog posts."""
    model_type = Post

async def create_post(db_session: AsyncSession, title: str, content: str, author_id: UUID) -> Post:
    repository = PostRepository(session=db_session)
    return await repository.add(
        Post(title=title, content=content, author_id=author_id), auto_commit=True
    )
```

## Filtering and Querying

Advanced Alchemy provides powerful filtering capabilities:

```python
import datetime

async def get_recent_posts(db_session: AsyncSession) -> list[Post]:
    repository = PostRepository(session=db_session)

    # Create filter for posts from last week
    return await repository.list(
        Post.published == True,
        Post.created_at > (datetime.datetime.utcnow() - timedelta(days=7))
    )
```

## Pagination

[list_and_count]{.title-ref} enables us to quickly create paginated
queries that include a total count of rows.

```python
from advanced_alchemy.filters import LimitOffset

async def get_paginated_posts(
    db_session: AsyncSession,
    page: int = 1,
    page_size: int = 20
) -> tuple[list[Post], int]:
    repository = PostRepository(session=db_session)

    offset = (page - 1) * page_size

    # Get page of results and total count
    results, total = await repository.list_and_count(
        LimitOffset(offset=offset, limit=page_size)
    )

    return results, total
```

## Bulk Operations

Repositories support efficient bulk operations:

## Add Many

```python
async def create_posts(db_session: AsyncSession, data: list[tuple[str, str, UUID]]) -> Sequence[Post]:
    repository = PostRepository(session=db_session)

    # Create posts
    return await repository.add_many(
        [Post(title=title, content=content, author_id=author_id) for title, content, author_id in data],
        auto_commit=True
    )
```

## Update Many

```python
async def publish_posts(db_session: AsyncSession, post_ids: list[int]) -> list[Post]:
    repository = PostRepository(session=db_session)

    # Fetch posts to update
    posts = await repository.list(Post.id.in_(post_ids), published =False)

    # Update all posts
    for post in posts:
        post.published = True

    return await repository.update_many(posts)
```

## Delete Many

```python
async def delete_posts(db_session: AsyncSession, post_ids: list[int]) -> list[Post]:
    repository = PostRepository(session=db_session)

    return await repository.delete_many(Post.id.in_(post_ids))
```

## Delete Where

```python
async def delete_unpublished_posts (db_session: AsyncSession) -> list[Post]:
    repository = PostRepository(session=db_session)

    return await repository.delete_where(Post.published == False)
```

## Transaction Management

```python
async def create_post_with_tags(
    db_session: AsyncSession,
    title: str,
    content: str,
    tag_names: list[str]
) -> Post:
    # Both repositories share the same transaction
    post_repo = PostRepository(session=db_session)
    tag_repo = TagRepository(session=db_session)

    async with db_session.begin():
        # Create or get existing tags
        tags = []
        for name in tag_names:
            tag = await tag_repo.get_one_or_none(name=name)
            if not tag:
                tag = await tag_repo.add(Tag(name=name, slug=slugify(name)))
            tags.append(tag)

        # Create post with tags
        post = await post_repo.add(
            Post(title=title, content=content, tags=tags),
            auto_commit=True
        )

        return post
```

::: seealso
This is just to illustrate the concept. In practice,
`UniqueMixin`{.interpreted-text role="class"} should be used to handle
this lookup even more easily. See `using_unique_mixin`{.interpreted-text
role="ref"}.
:::

## Specialized Repositories

Advanced Alchemy provides specialized repositories for common patterns.

### Slug Repository

For models using the `SlugKey`{.interpreted-text role="class"} mixin,
there is a specialized Slug repository that adds a `get_by_slug` method:

```python
from advanced_alchemy.repository import SQLAlchemyAsyncSlugRepository

class ArticleRepository(SQLAlchemyAsyncSlugRepository[Article]):
    """Repository for articles with slug-based lookups."""
    model_type = Article

async def get_article_by_slug(db_session: AsyncSession, slug: str) -> Article:
    repository = ArticleRepository(session=db_session)
    return await repository.get_by_slug(slug)
```

## Query Repository

For complex custom queries:

```python
from advanced_alchemy.repository import SQLAlchemyAsyncQueryRepository
from sqlalchemy import select, func

async def get_posts_per_author(db_session: AsyncSession) -> list[tuple[UUID, int]]:
    repository = SQLAlchemyAsyncQueryRepository(session=db_session)
    return await repository.list(select(Post.author_id, func.count(Post.id)).group_by(Post.author_id))
```

This covers the core functionality of repositories. The next section
will explore services, which build upon repositories to provide
higher-level business logic and data transformation.

# Types

Advanced Alchemy provides several custom SQLAlchemy types.

All types include:

- Proper Python type annotations for modern IDE support
- Automatic dialect-specific implementations
- Consistent behavior across different database backends
- Integration with SQLAlchemy\'s type system

Here\'s a short example using multiple types:

```python
from typing import Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from advanced_alchemy.base import DefaultBase
from advanced_alchemy.types import (
    DateTimeUTC,
    EncryptedString,
    GUID,
    JsonB,
    StoredObject,
    FileObject,
)

class User(DefaultBase):
    __tablename__ = "users"
    id: Mapped[UUID] = mapped_column(GUID, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTimeUTC)
    password: Mapped[str] = mapped_column(EncryptedString(key="secret-key"))
    preferences: Mapped[dict] = mapped_column(JsonB)
    avatar: Mapped[Optional[FileObject]] = mapped_column(StoredObject(backend="local_store"))
```

## DateTime UTC

- Ensures all datetime values are stored in UTC
- Requires timezone information for input values
- Automatically converts stored values to UTC timezone
- Returns timezone-aware datetime objects

```python
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from advanced_alchemy.base import DefaultBase
from advanced_alchemy.types import DateTimeUTC

class MyModel(DefaultBase):
    created_at: Mapped[datetime] = mapped_column(DateTimeUTC)
```

## Encrypted Types

Two types for storing encrypted data with support for multiple
encryption backends:

### EncryptedString

For storing encrypted string values with configurable length.

```python
from sqlalchemy.orm import Mapped, mapped_column
from advanced_alchemy.base import DefaultBase
from advanced_alchemy.types import EncryptedString

class MyModel(DefaultBase):
    secret: Mapped[str] = mapped_column(EncryptedString(key="my-secret-key"))
```

### EncryptedText

For storing larger encrypted text content (CLOB).

```python
from sqlalchemy.orm import Mapped, mapped_column
from advanced_alchemy.base import DefaultBase
from advanced_alchemy.types import EncryptedText

class MyModel(DefaultBase):
    large_secret: Mapped[str] = mapped_column(EncryptedText(key="my-secret-key"))
```

### Encryption Backends

Two encryption backends are available:

- `FernetBackend <advanced_alchemy.types.encrypted_string.FernetBackend>`{.interpreted-text
  role="class"}: Uses Python\'s [cryptography](https://cryptography.io/)
  library with Fernet encryption
- `PGCryptoBackend <advanced_alchemy.types.encrypted_string.PGCryptoBackend>`{.interpreted-text
  role="class"}: Uses PostgreSQL\'s
  [pgcrypto](https://www.postgresql.org/docs/current/pgcrypto.html)
  extension (PostgreSQL only)

## GUID

A platform-independent GUID/UUID type that adapts to different database
backends:

- PostgreSQL/DuckDB/CockroachDB: Uses native UUID type
- MSSQL: Uses UNIQUEIDENTIFIER
- Oracle: Uses RAW(16)
- Others: Uses BINARY(16) or CHAR(32)

```python
from sqlalchemy.orm import Mapped, mapped_column
from advanced_alchemy.base import DefaultBase
from advanced_alchemy.types import GUID
from uuid import UUID

class MyModel(DefaultBase):
    __tablename__ = "my_model"
    id: Mapped[UUID] = mapped_column(GUID, primary_key=True)
```

## BigInt Identity

A BigInteger type that automatically falls back to Integer for SQLite:

```python
from sqlalchemy.orm import Mapped, mapped_column
from advanced_alchemy.base import DefaultBase
from advanced_alchemy.types import BigIntIdentity

class MyModel(DefaultBase):
    __tablename__ = "my_model"
    id: Mapped[int] = mapped_column(BigIntIdentity, primary_key=True)
```

## JsonB

A JSON type that uses the most efficient JSON storage for each database:

- PostgreSQL/CockroachDB: Uses native JSONB
- Oracle: Uses Binary JSON (BLOB with JSON constraint)
- Others: Uses standard JSON type

```python
from sqlalchemy.orm import Mapped, mapped_column
from advanced_alchemy.base import DefaultBase
from advanced_alchemy.types import JsonB

class MyModel(DefaultBase):
    data: Mapped[dict] = mapped_column(JsonB)
```

## Password Hash

A type for storing password hashes with configurable backends. Currently
supports:

- `~advanced_alchemy.types.password_hash.pwdlib.PwdlibHasher`{.interpreted-text
  role="class"}: Uses [pwdlib](https://frankie567.github.io/pwdlib/)
- `~advanced_alchemy.types.password_hash.argon2.Argon2Hasher`{.interpreted-text
  role="class"}: Uses
  [argon2-cffi](https://argon2-cffi.readthedocs.io/en/stable/)
- `~advanced_alchemy.types.password_hash.passlib.PasslibHasher`{.interpreted-text
  role="class"}: Uses
  [passlib](https://passlib.readthedocs.io/en/stable/)

```python
from sqlalchemy.orm import Mapped, mapped_column
from advanced_alchemy.base import DefaultBase
from advanced_alchemy.types import PasswordHash
from advanced_alchemy.types.password_hash.pwdlib import PwdlibHasher
from pwdlib.hashers.argon2 import Argon2Hasher as PwdlibArgon2Hasher

class MyModel(DefaultBase):
    __tablename__ = "my_model"
    password: Mapped[str] = mapped_column(
    PasswordHash(backend=PwdlibHasher(hasher=PwdlibArgon2Hasher()))
)
```

## File Object Storage

Advanced Alchemy provides a powerful file object storage system through
the `StoredObject`{.interpreted-text role="class"} type. This system
supports multiple storage backends and provides automatic file cleanup.

### Basic Usage

```python
from typing import Optional
from advanced_alchemy.base import UUIDBase
from advanced_alchemy.types.file_object import FileObject, FileObjectList, StoredObject
from sqlalchemy.orm import Mapped, mapped_column

class Document(UUIDBase):
    __tablename__ = "documents"

    # Single file storage
    attachment: Mapped[Optional[FileObject]] = mapped_column(
        StoredObject(backend="s3"),
        nullable=True
    )

    # Multiple file storage
    images: Mapped[Optional[FileObjectList]] = mapped_column(
        StoredObject(backend="s3", multiple=True),
        nullable=True
    )
```

### Storage Backends

Two storage backends are available:

#### FSSpec Backend

The FSSpec backend uses the
[fsspec](https://filesystem-spec.readthedocs.io/) library to support
various storage systems:

```python
import fsspec
from advanced_alchemy.types.file_object.backends.fsspec import FSSpecBackend
from advanced_alchemy.types.file_object import storages

# Local filesystem
storages.register_backend(FSSpecBackend(fs=fsspec.filesystem("file"), key="local"))
# S3 storage
fs = fsspec.S3FileSystem(
    anon=False,
    key="your-access-key",
    secret="your-secret-key",
    endpoint_url="https://your-s3-endpoint",
)
storages.register_backend(FSSpecBackend(fs=fs, key="s3", prefix="your-bucket"))
```

#### Obstore Backend

The Obstore backend provides a simple interface for object storage:

```python
from advanced_alchemy.types.file_object.backends.obstore import ObstoreBackend
from advanced_alchemy.types.file_object import storages

# Local storage
storages.register_backend(ObstoreBackend(
    key="local",
    fs="file:///path/to/storage",
))

# S3 storage
storages.register_backend(ObstoreBackend(
    key="s3",
    fs="s3://your-bucket/",
    aws_access_key_id="your-access-key",
    aws_secret_access_key="your-secret-key",
    aws_endpoint="https://your-s3-endpoint",
))
```

### Metadata

File objects support metadata storage:

```python
file_obj = FileObject(
    backend="local_test_store",
    filename="test.txt",
    metadata={
        "category": "document",
        "tags": ["important", "review"],
    },
)

# Update metadata
file_obj.update_metadata({"priority": "high"})
```

### Automatic Cleanup

When a file object is removed from a model or the model is deleted, the
associated file is automatically saved or deleted from storage:

**Note:** The listener events are automatically configured when using
any of the framework adapters. You may manually configure these events
by calling the [configure_listeners]{.title-ref} method on the
configuration class.

```python
# Update file
doc.attachment = FileObject(
    backend="local_test_store",
    filename="test.txt",
    content=b"Hello, World!",
)
await db_session.commit()  # new file is saved, old file is automatically deleted

# Clear file
doc.attachment = None
await db_session.commit()  # File is automatically deleted

# Delete model
await db_session.delete(doc)
await db_session.commit()  # All associated files are automatically deleted
```

### Manual File Operations

The FileObject class provides various operations for managing files if
you don\'t want to use the automatic listeners (or can\'t use them):

```python
# Save a file
file_obj = FileObject(
    backend="local_test_store",
    filename="test.txt",
    content=b"Hello, World!",
)
await file_obj.save_async()

# Get file content
content = await file_obj.get_content_async()

# Delete a file
await file_obj.delete_async()

# Get signed URL
url = await file_obj.sign_async(expires_in=3600)  # URL expires in 1 hour
```

## Using Types with Alembic

If you are not using Advanced Alchemy\'s built-in [alembic]{.title-ref}
templates, you need to properly configure your `script.py.mako`
template. The key is to make the custom types available through the `sa`
namespace that Alembic uses.

### Type Aliasing

In your `script.py.mako`, you\'ll need both the imports and the type
aliasing:

``` {.python caption="script.py.mako"}
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
import sqlalchemy as sa
# ...

# Import the types
from advanced_alchemy.types import (
    EncryptedString,
    EncryptedText,
    GUID,
    ORA_JSONB,
    DateTimeUTC,
    StoredObject,
)

# Create aliases in the sa namespace
sa.GUID = GUID
sa.DateTimeUTC = DateTimeUTC
sa.ORA_JSONB = ORA_JSONB
sa.EncryptedString = EncryptedString
sa.EncryptedText = EncryptedText
sa.StoredObject = StoredObject
# ...
```

:::: note
::: title
Note
:::

These assignments are necessary because alembic uses the `sa` namespace
when generating migrations. Without these aliases, Alembic might not
properly reference the custom types.
::::

This allows you to use the types in migrations like this:

```python
# In generated migration file
def upgrade():
    op.create_table(
        'users',
        sa.Column('id', sa.GUID(), primary_key=True),
        sa.Column('created_at', sa.DateTimeUTC(), nullable=False),
        sa.Column('secret', sa.EncryptedString(), nullable=True),
        sa.Column('avatar', sa.StoredObject(backend="local_store"), nullable=True),
    )
```

##### Flask Integration

Advanced Alchemy provides seamless integration with Flask applications
through its Flask extension.

## Installation

The Flask extension is included with Advanced Alchemy by default. No
additional installation is required.

## Basic Usage

Here\'s a basic example of using Advanced Alchemy with Flask:

```python
from flask import Flask
from sqlalchemy import select
from advanced_alchemy.extensions.flask import (
    AdvancedAlchemy,
    SQLAlchemySyncConfig,
    EngineConfig,
)

app = Flask(__name__)
alchemy_config = SQLAlchemySyncConfig(connection_string="sqlite:///local.db", commit_mode="autocommit", create_all=True)
alchemy = AdvancedAlchemy(alchemy_config, app)

# Use standard SQLAlchemy session in your routes
@app.route("/users")
def list_users():
    db_session = alchemy.get_sync_session()
    users = db_session.execute(select(User))
    return {"users": [user.dict() for user in users.scalars()]}
```

## Multiple Databases

Advanced Alchemy supports multiple database configurations:

:::: note
::: title
Note
:::

The `bind_key` option is used to specify the database to use for a given
session.

When using multiple databases and you do not have at least one database
with a `bind_key` of `default`, and exception will be raised when
calling `db.get_session()` without a bind key.

This only applies when using multiple configuration. If you are using a
single configuration, the engine will be returned even if the `bind_key`
is not `default`.
::::

```python
configs = [
    SQLAlchemySyncConfig(connection_string="sqlite:///users.db", bind_key="users"),
    SQLAlchemySyncConfig(connection_string="sqlite:///products.db", bind_key="products"),
]

alchemy = AdvancedAlchemy(configs, app)

# Get session for specific database
users_session = alchemy.get_sync_session("users")
products_session = alchemy.get_sync_session("products")
```

## Async Support

Advanced Alchemy supports async SQLAlchemy with Flask:

```python
from advanced_alchemy.extensions.flask import (
    AdvancedAlchemy,
    SQLAlchemyAsyncConfig,
)
from sqlalchemy import select

app = Flask(__name__)
alchemy_config = SQLAlchemyAsyncConfig(connection_string="postgresql+asyncpg://user:pass@localhost/db", create_all=True)
alchemy = AdvancedAlchemy(alchemy_config, app)

# Use async session in your routes
@app.route("/users")
async def list_users():
    db_session = alchemy.get_async_session()
    users = await db_session.execute(select(User))
    return {"users": [user.dict() for user in users.scalars()]}
```

You can also safely use an AsyncSession in your routes within a sync
context.

:::: warning
::: title
Warning
:::

This is experimental and may change in the future.
::::

```python
@app.route("/users")
def list_users():
    db_session = alchemy.get_async_session()
    users = alchemy.portal.call(db_session.execute, select(User))
    return {"users": [user.dict() for user in users.scalars()]}
```

## Configuration

### SQLAlchemy Configuration

Both sync and async configurations support these options:

  Option            Type                                                      Description                         Default
  ----------------- --------------------------------------------------------- ----------------------------------- -------------
  `engine_config`   `EngineConfig`                                            SQLAlchemy engine configuration     Required
  `bind_key`        `str`                                                     Key for multiple database support   \"default\"
  `create_all`      `bool`                                                    Create tables on startup            `False`
  `commit_mode`     `"autocommit", "autocommit_include_redirect", "manual"`   Session commit behavior             `"manual"`

### Commit Modes

The `commit_mode` option controls how database sessions are committed:

- `"manual"` (default): No automatic commits
- `"autocommit"`: Commit on successful responses (2xx status codes)
- `"autocommit_include_redirect"`: Commit on successful responses and
  redirects (2xx and 3xx status codes)

## Services

The `FlaskServiceMixin` adds Flask-specific functionality to services:

Here\'s an example of a service that uses the `FlaskServiceMixin` with
all CRUD operations, route pagination, and msgspec serialization for
JSON

```python
import datetime
from typing import Optional
from uuid import UUID

from msgspec import Struct
from flask import Flask
from sqlalchemy.orm import Mapped, mapped_column
from advanced_alchemy.extensions.flask import (
    AdvancedAlchemy,
    FlaskServiceMixin,
    service,
    repository,
    SQLAlchemySyncConfig,
    base,
)

class Author(base.UUIDBase):
    """Author model."""

    name: Mapped[str]
    dob: Mapped[Optional[datetime.date]]

class AuthorSchema(Struct):
    """Author schema."""

    name: str
    id: Optional[UUID] = None
    dob: Optional[datetime.date] = None


class AuthorService(FlaskServiceMixin, service.SQLAlchemySyncRepositoryService[Author]):
    class Repo(repository.SQLAlchemySyncRepository[Author]):
        model_type = Author

    repository_type = Repo

app = Flask(__name__)
alchemy_config = SQLAlchemySyncConfig(connection_string="sqlite:///local.db", commit_mode="autocommit", create_all=True)
alchemy = AdvancedAlchemy(alchemy_config, app)


@app.route("/authors", methods=["GET"])
def list_authors():
    """List authors with pagination."""
    page, page_size = request.args.get("currentPage", 1, type=int), request.args.get("pageSize", 10, type=int)
    limit_offset = filters.LimitOffset(limit=page_size, offset=page_size * (page - 1))
    service = AuthorService(session=alchemy.get_sync_session())
    results, total = service.list_and_count(limit_offset)
    response = service.to_schema(results, total, filters=[limit_offset], schema_type=AuthorSchema)
    return service.jsonify(response)


@app.route("/authors", methods=["POST"])
def create_author():
    """Create a new author."""
    service = AuthorService(session=alchemy.get_sync_session())
    obj = service.create(**request.get_json())
    return service.jsonify(obj)


@app.route("/authors/<uuid:author_id>", methods=["GET"])
def get_author(author_id: UUID):
    """Get an existing author."""
    service = AuthorService(session=alchemy.get_sync_session(), load=[Author.books])
    obj = service.get(author_id)
    return service.jsonify(obj)


@app.route("/authors/<uuid:author_id>", methods=["PATCH"])
def update_author(author_id: UUID):
    """Update an author."""
    service = AuthorService(session=alchemy.get_sync_session(), load=[Author.books])
    obj = service.update(**request.get_json(), item_id=author_id)
    return service.jsonify(obj)


@app.route("/authors/<uuid:author_id>", methods=["DELETE"])
def delete_author(author_id: UUID):
    """Delete an author."""
    service = AuthorService(session=alchemy.get_sync_session())
    service.delete(author_id)
    return "", 204
```

The `jsonify` method is analogous to Flask\'s `jsonify` function.
However, this implementation will serialize with the configured Advanced
Alchemy serialize (i.e. Msgspec or Orjson based on installation).

## Database Migrations

When the extension is configured for Flask, database commands are
automatically added to the Flask CLI. These are the same commands
available to you when running the `alchemy` standalone CLI.

Here\'s an example of the commands available to Flask

``` bash
# Initialize migrations
flask database init

# Create a new migration
flask database revision --autogenerate -m "Add users table"

# Apply migrations
flask database upgrade

# Revert migrations
flask database downgrade

# Show migration history
flask database history

# Show all commands
flask database --help
```
