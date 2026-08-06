# AIpress24 Python client

A tiny, **dependency-free** client for the AIpress24 public API (`/api/v1`). It
uses only the Python standard library, so you can `pip install` it or just vendor
the `aipress24_client/` package.

The transport (`Client`, `Page`, `ApiError`) is hand-written and stable. The
drift-prone parts — the collection list and the per-resource typed models
(`aipress24_client/_generated.py`) — are **generated from the OpenAPI spec**:
run `make api-sdk` from the repo root to regenerate. A test asserts the
committed file stays in sync with the spec, so the client can't silently drift.

## Install

```bash
pip install ./sdk/python          # from a checkout
# or vendor aipress24_client/__init__.py directly into your project
```

## Authentication

The API is authenticated with a **bearer token**. Ask an AIpress24 administrator
to issue one (they run `flask api-token issue --email you@example.com`). A token
carries scopes — `read:content`, `read:organisations`, `read:directory`,
`read:self` (your own `/me` data) and `write:content` (author & publish your own
content) — and can be revoked at any time.

## Usage

```python
from aipress24_client import Client, ApiError

api = Client(token="a24_your_token_here", base_url="https://aipress24.com")

# Discovery entry point (public): link relations + docs URLs.
print(api.root()["_links"].keys())

# One page (offset/limit pagination, HATEOAS _links in every payload):
page = api.articles(limit=10)
print(page.total, "articles;", len(page), "on this page")
for article in page:
    print(article["title"], "->", article["_links"]["self"]["href"])

# Walk every page automatically, following the `next` link:
for member in api.iter("members", limit=50):
    print(member["full_name"], member.get("job_title"))

# Fetch a single resource:
one = api.article(page.items[0]["id"])

# Errors surface as ApiError with the HTTP status + JSON body:
try:
    api.members()  # needs the read:directory scope
except ApiError as exc:
    print(exc.status, exc.payload)
```

## Public read resources

| Method | Endpoint | Scope |
|---|---|---|
| `articles()` / `article(id)` | `/api/v1/articles` | `read:content` |
| `press_releases()` / `press_release(id)` | `/api/v1/press-releases` | `read:content` |
| `events()` / `event(id)` | `/api/v1/events` | `read:content` |
| `organisations()` / `organisation(id)` | `/api/v1/organisations` | `read:organisations` |
| `business_walls()` / `business_wall(id)` | `/api/v1/business-walls` | `read:organisations` |
| `members()` / `member(id)` | `/api/v1/members` | `read:directory` |

## Owner-scoped data & writes (`/me`)

`me()` returns your own profile (`read:self`). Your own records — in any status,
including drafts — are read generically (`read:self`), and the content types can
be authored and published (`write:content`). `collection` is a path segment such
as `me/press-releases`, `me/articles` or `me/events`.

| Method | Endpoint | Scope |
|---|---|---|
| `me()` | `GET /api/v1/me` | `read:self` |
| `list("me/articles")` / `get_one("me/articles", id)` | own articles (also `me/press-releases`, `me/events`, `me/enquiry-notices`, `me/missions`, `me/projects`, `me/jobs`, `me/products`) | `read:self` |
| `create(collection, data)` | `POST /api/v1/{collection}` | `write:content` |
| `update(collection, id, data)` | `PATCH /api/v1/{collection}/{id}` | `write:content` |
| `publish(collection, id)` / `unpublish(collection, id)` | `POST …/{id}/publish` \| `/unpublish` | `write:content` |
| `delete(collection, id)` | `DELETE /api/v1/{collection}/{id}` | `write:content` |

```python
# Author a press release on your own behalf, then publish it.
pr = api.create(
    "me/press-releases", {"titre": "Acme launches …", "contenu": "<p>…</p>"}
)
api.publish("me/press-releases", pr["id"])
```

Interactive documentation (OpenAPI) is served live at
`https://aipress24.com/api/v1/docs` (Swagger UI) and `/api/v1/redoc`, with the raw
spec at `/api/v1/openapi.json`.
