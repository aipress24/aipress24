# ADR 004: Public API — Data Access, Visibility, and SDK Generation

**Status**: Accepted
**Type**: Architecture
**Created**: 2026-07-03
**Authors**: Stefane Fermigier <sf@abilian.com>
**Related-ADRs**: 001

## Context

Aipress24 serves the press and PR ecosystem — journalists, communicants, leaders and experts, academics, transformers — combining a press CMS, a professional social network, and a marketplace. Today almost all of its value is reached through the web UI.

The original RFP called for a third-party **integration API** so external providers could interoperate with the platform, but the intent was never specified further: there is no agreed list of consumers or endpoints. The shape of such an API therefore has to be inferred from the domain, which requires some deliberate guesswork. Plausible consumers include news aggregators and media-monitoring ("veille") services syndicating published articles and press releases; PR tools tracking their clients' published coverage and releases; journalist/organisation directory or CRM tools syncing the public professional directory; event calendars pulling published events; and job/mission boards pulling published marketplace offers. The common thread is letting the ecosystem's existing tools read Aipress24's public content and directories programmatically, rather than forcing every partner through the UI.

There is a second, architectural reason to value such an API even without a named consumer: it exposes the domain **without the UI layer**, a major source of accidental complexity. Designing a clean, versioned, UI-free read model is a forcing function that makes the business domain explicit — most sharply, it forces a single, unambiguous answer to "what content is *publicly visible*?", a question the UI currently answers implicitly and inconsistently across many code paths.

An initial read-only, token-authenticated, OpenAPI-documented API (`app.modules.api_v1`, at `/api/v1`) now exists. This ADR is not about whether to have the API; it records two decisions about *how* it is built: how its read layer relates to the domain, and how the client SDK is produced.

## Motivation

The initial implementation has the read layer — hand-written `select(...)` statements in `api_v1/queries.py` — re-derive the "publicly visible" gate (`status == PUBLIC`, `active`, `deleted_at IS NULL`, …) for each resource. That is exactly the "what is publicly visible?" question above, answered a third time and differently — and already wrong. The domain's canonical predicate is `is_public()` in `app/modules/search/adapters.py` (what decides search-index membership), registered per type for every resource the API exposes. For content it is stricter than the API's gate — `_is_publicly_visible()` requires `status == PUBLIC` **and** `published_at` set **and** not past expiry — so the API serves expired articles the site's own search hides. For organisations, `is_public(Organisation)` gates on `deleted_at IS NULL` while the API used `active == True`; for members, the swork directory's `get_base_statement()` (active + not-clone + not-deleted, with eager-loads) already existed and the API hand-copied it.

Visibility — and, more broadly, *authorization* — rules change (moderation, expiry, soft-delete, paywalls, ownership). Every place that re-encodes them silently diverges, and for an API the stakes are higher than for the UI: a machine-readable endpoint that discloses draft, expired, for-sale, or otherwise private content is a security exposure, not just a bug. The access rules must have a single owner in the domain, with the API consuming them.

A secondary gap compounds this: `events` and `biz` have **no repositories at all** (unlike `wire`, core, and `bw`), so their visibility lives only in view code and the search adapters — nowhere the API can reuse. And the same "drift" risk applies to the client SDK: a hand-maintained client silently falls out of step with the served OpenAPI contract.

## Decision

Adopt **Option A: delegate to the domain.** The API owns no visibility logic; each read resolves a domain repository and calls a visibility-gated method. Concretely:

- Define one query-level predicate, `app/models/content/visibility.py:published_filters`, mirroring `is_public`/`_is_publicly_visible` (status + published_at + not-expired), parameterised by the family's expiry column (wire `expires_at`, `Publishable` content `expired_at`).
- Add a shared `PublishableRepository` base exposing `list_published` / `get_published` over that predicate.
- Give `events` and `biz` real repositories (the missing layer), using it.
- Reuse existing domain predicates for the rest: `UserRepository.public_member_filters` / `list_public_members` (shared with the swork members directory), `OrganisationRepository.list_public`, and a `BusinessWallRepository.list_active`.
- Reduce `api_v1/queries.py` to a thin adapter that resolves these repositories.

The governing tenet is broader than visibility: wherever the API exposes data, the decision of *who may see it* is made by the domain's own checks — the visibility predicate today, and ownership / entitlement (`user_can_read_full`) / role checks as the API grows past the public tier — never re-implemented in the API layer. This is what makes access parity with the UI (see Security Implications) achievable rather than aspirational.

Separately, adopt the second decision: the client SDK is **generated statically from the served OpenAPI document**, not hand-maintained.

## Detailed Design

### Single visibility predicate

`published_filters(model, *, expiry_attr, now)` returns SQLAlchemy filters — `status == PUBLIC`, `published_at IS NOT NULL` (when present), and `expiry IS NULL OR expiry > now`. It is pure (no Flask import; it lives in the models layer, respecting the ADR-001 layering) and is the query-level twin of the per-object `search.adapters.is_public`. The two encode the same rule; a comment cross-references them.

### Repository layer

`PublishableRepository(Repository[ModelT])` (in `app/services/repositories/`) provides `list_published(limit, offset) -> (rows, total)` and `get_published(id)`, both delegating to `published_filters`. Content repositories subclass it and set `model_type` (plus `expiry_attr` when not the wire default):

- `wire`: `ArticlePostRepository`, `PressReleasePostRepository`
- `events` (new): `EventPostRepository`
- `biz` (new): `MissionOffer` / `ProjectOffer` / `JobOffer` / `EditorialProduct` repositories

Non-content resources keep their own criteria, but each in one place: members and organisations on `UserRepository` / `OrganisationRepository` (svcs-registered, resolved via the container); business walls on `BusinessWallRepository` (not svcs-registered — the bw module uses the advanced-alchemy service layer — so the API instantiates it against the request session).

### API adapter

`api_v1/queries.py` resolves the repository (`container.get(...)`, or direct construction for bw) and returns its result. It owns no `where(...)`. The rest of the API (auth, scopes, schemas, HATEOAS, error handling) is unchanged.

### SDK generation

The spec is served at `/api/v1/openapi.json` and exportable offline via `api_v1.current_openapi_json()`. A `make api-sdk` target will export the spec, run a generator, and a CI check will fail if regeneration produces a diff (so a spec change unreflected in the SDK breaks the build).

## Consequences

### Positive

- One owner for "publicly visible"; the API cannot drift from the site or search.
- Fixed real drift: expired and never-`published_at` content are now excluded, and organisation visibility matches the domain.
- `events` and `biz` gain the repository layer the other content modules already had; the shared predicate removes duplication and opens a path to converging the view/search/API definitions.
- The SDK becomes a build artifact with a CI drift guard.

### Negative

- Touches several domain modules (wire / events / biz / bw / swork / core) — a broader change than an API-local fix.
- A deliberate behaviour change: organisations now use `deleted_at IS NULL` (the domain criterion) rather than `active == True`, so inactive-but-not-deleted organisations are now returned.
- Two encodings of the visibility rule remain (the per-object `is_public` and the SQL `published_filters`), inherent to the object-vs-query split; mitigated by co-location and cross-references.

## Security Implications

**Governing principle — access parity with the UI.** A token authenticates *as its user*; the API must return exactly what that user could obtain by logging into the UI — no more, no less. It must never be a side door that discloses data a user could not otherwise reach. This is enforceable precisely because access decisions are delegated to the domain's checks (the Decision's tenet), rather than re-derived in the API.

The data partitions into tiers, each gated by the *same domain check the UI uses*:

- **Public tier** — published content, active organisations and Business Walls, the listable member directory: what any authenticated user sees. This is v1's surface, gated by the shared visibility predicate.
- **Owner-scoped private data** — a user's own drafts, `avis d'enquête`, and other private items: reachable *only* by their owner, through that owner's token, and by no one else. Drafts and private data must **never** appear on the public tier.
- **Entitlement-gated ("for sale") content** — a paid article's body must be gated by the same purchase/ownership check the UI applies (`wire.services.article_access.user_can_read_full`), falling back to the preview (`truncate_body`) otherwise. `status == PUBLIC` alone must not unlock for-sale content.
- **Cross-user PII** — contact details (email, phone) and raw KYC blobs are redacted by field allowlist, mirroring the UI's per-viewer contact gating.

**Enforced (was a v1 gap):** the news schema now serialises the full `content` only when `user_can_read_full(token_user, post)` (author, admin, or a paid/gifted consultation), and `truncate_body(...)` otherwise — reusing the domain check rather than re-implementing it, and matching the site's paywall (including its "show the full body when the paywall is not live" behaviour). A regression test asserts a paywalled body is withheld from a non-entitled token and released to the author. Before this, `ArticleSchema` dumped the full body of every published article, disclosing for-sale content the UI truncates.

**Standing item:** deleting a source newsroom article does not unpublish its wire mirror, so a soft-deleted article can remain `status == PUBLIC` and be served. This predates the API (it affects the News web portal and the search index too) and must be fixed in the wire sync layer.

## Alternatives Considered

- **Option B — Align `queries.py` in place**: keep the API-local query layer but make it match `is_public` semantics. Smallest blast radius, but leaves a second copy of the rule that can re-drift. Rejected: removes the current symptom, not the drift.
- **Option C — Back listings with the wesh search index**: list from the index (the canonical public set) and rehydrate from the DB. Maximal alignment, but the BM25 index is not built for stable resource listing/ordering/id-filtering, and it couples the API to search. Rejected as overkill for v1.
- **Option D — Drop or scope down the API**: ship nothing, or content-only. Rejected: discards working, tested, reviewed code with real integration value.

## Unresolved Questions

- SDK generator choice: `openapi-python-client` (typed, well-maintained, but pulls `httpx` / `attrs` into the generated client) vs a custom script (`datamodel-code-generator` plus a thin template — lighter, more to own). To be decided before wiring `make api-sdk`.

## Future Work

- Extend the API past the public tier with **owner-scoped** access — a user's own drafts, `avis d'enquête`, etc., keyed on the token's identity and gated by the domain's ownership/authorization checks — so a user reaches their own private data (and only their own) via the API, matching the UI.
- Migrate the existing `events` and `biz` **views** onto the new repositories so their inline `status == PUBLIC` queries also converge on `published_filters`.
- Fix the wire sync layer to unpublish (or delete) the mirror on source deletion, removing the soft-deleted-content exposure.
- Wire SDK generation and the CI drift check once the generator is chosen.

## References

- `app/modules/search/adapters.py` — `is_public` / `_is_publicly_visible` (canonical per-object predicate)
- `app/models/content/visibility.py` — `published_filters` (query-level predicate)
- ADR 001 — module layering and import discipline (the API module is an import-linter leaf)
- flask-smorest, marshmallow, apispec — the API framework stack
