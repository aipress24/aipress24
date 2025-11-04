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

