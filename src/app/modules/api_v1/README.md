<!--
Copyright (c) 2025, Abilian SAS & TCA
SPDX-License-Identifier: AGPL-3.0-only
-->

# `api_v1` — the public REST API (`/api/v1`)

A versioned, OpenAPI-documented, token-authenticated, **read-only** REST API for third-party integrations. It is deliberately isolated: it depends on the business modules (wire, events, biz, bw, swork, core models/services) but **nothing depends on it** — enforced by an import-linter contract (`setup.cfg`, contract 2).

This is separate from the internal `app.modules.api` blueprint (`/api`), which is session-cookie-authenticated and only serves the HTML front-end (likes, Trix uploads).

## Design at a glance

| Concern | Choice |
|---|---|
| Framework | [flask-smorest](https://flask-smorest.readthedocs.io/) (marshmallow 4 + webargs + apispec) |
| Docs | OpenAPI 3 at `/api/v1/openapi.json`; Swagger UI at `/api/v1/docs`; ReDoc at `/api/v1/redoc` |
| Auth | `Authorization: Bearer <token>` — dedicated `ApiToken` (hashed, scoped, expirable, revocable). No session, no CSRF. |
| Surface | Read-only (GET) in v1 |
| Serialization | Allowlist marshmallow schemas — PII is redacted by omission |
| Pagination | offset/limit, `{items, total, count, limit, offset, _links}` envelope |
| Hypermedia | HAL-style `_links` on every payload; discovery entry point at `/api/v1/` |
| Errors | JSON, scoped to this blueprint only (the HTML site is untouched) |

## Wiring

The blueprint is **not** exposed as a top-level `blueprint` attribute (which the app's auto-discovery would register with a plain `app.register_blueprint`, losing the OpenAPI paths). Instead it is registered through the `register_on_app` hook using a `ScopedApi` (a flask-smorest `Api` subclass that does *not* hijack app-wide error handling). See `__init__.py`.

## Files

| File | Responsibility |
|---|---|
| `__init__.py` | Blueprint, token `before_request`, JSON errors, `ScopedApi` + `register_on_app` |
| `security.py` | Scopes, token minting/hashing, `resolve_token`, per-request identity (functional core) |
| `models.py` | `ApiToken` (table `api_token`) |
| `schemas.py` | Allowlist marshmallow schemas + HATEOAS link helpers + collection envelope |
| `queries.py` | Thin adapter that resolves the **domain repositories** — owns no visibility logic |
| `resources.py` | The MethodView resources + the discovery root |
| `cli.py` | `flask api-token issue|list|revoke` |

## Scopes

| Scope | Grants |
|---|---|
| `read:content` | articles, press releases, events |
| `read:organisations` | organisations, business walls |
| `read:directory` | member profiles |

## Resources (v1)

`articles`, `press-releases`, `events` (published only), `organisations` (active), `business-walls` (active), `members` (active, non-clone, non-deleted; contact details redacted). Each exposes `GET /{collection}` and `GET /{collection}/{id}`.

## Issuing a token

```bash
flask api-token issue --email editor@example.com \
    --name "Acme integration" --scopes read:content,read:directory --expires-days 365
```

The secret is printed once; only its SHA-256 hash is stored. Revoke with `flask api-token revoke <id>`.

## Client SDK

A dependency-free Python client lives at `sdk/python/` (`aipress24_client`). See its README.

## Data access

The API does **not** re-derive "what is publicly visible" — that lives in the domain and the API delegates to it, so it can't drift:

- content (articles, press releases, events) → `PublishableRepository.list_published/get_published`, gated by the single `app/models/content/visibility.py:published_filters` predicate (mirrors `search.adapters.is_public`);
- organisations / members → `OrganisationRepository.list_public` / `UserRepository.list_public_members` (the swork directory shares the same predicates);
- business walls → `BusinessWallRepository.list_active/get_active`.

`queries.py` just resolves the relevant repository and returns its result. See ADR 004.

## Adding a resource

1. Reuse (or add) a visibility-gated read on the **domain repository** — never re-implement the "public" filter here.
2. Add a thin delegator to `queries.py`.
3. Add an allowlist schema to `schemas.py` (+ its `make_collection_schema`).
4. Add a `MethodView` pair to `resources.py`, guarded by `_require(<scope>)`.
5. Link it from the discovery root and add tests in `tests/**/modules/api_v1/`.

## Operational notes

- Authenticating stamps `ApiToken.last_used_at` (one small write per request). Batch it if request volume ever makes that a concern.
- The Swagger UI / ReDoc pages load their assets from a CDN. Under the production Talisman CSP (`default-src 'self'`) those assets are blocked, so the interactive docs render blank in prod; `openapi.json` itself is always available. Relax the CSP for `/api/v1/docs` (or self-host the UI assets) if the rendered docs are needed in production.
- v1 exposes raw integer/UUID ids. Content Snowflake ids encode an approximate creation time and member ids are sequential; if enumeration becomes a concern, mint opaque ids at the boundary (`app/lib/base62.py`).
