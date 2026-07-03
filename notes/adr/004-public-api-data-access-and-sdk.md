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

A token-authenticated, OpenAPI-documented API (`app.modules.api_v1`, at `/api/v1`) now exists — read across the platform, plus owner-scoped writes for authoring/publishing one's own content. This ADR is not about whether to have the API; it records the decisions about *how* it is built: how its read **and** write layers relate to the domain (both delegate to the domain rather than re-deriving visibility or authorization), and how the client SDK is produced.

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

`PublishableRepository(Repository[ModelT])` (in `app/services/repositories/`) provides `list_published(limit, offset) -> (rows, total)` and `get_published(id)`, both delegating to `published_filters`. The lifecycle-content repositories subclass it and set `model_type` (plus `expiry_attr` when not the wire default):

- `wire`: `ArticlePostRepository`, `PressReleasePostRepository`
- `events` (new): `EventPostRepository`

**Marketplace is different**: it has no `published_at`/expiry — visibility is `status` alone (`is_public(MarketplaceContent)`). So the `biz` repositories (`MissionOffer` / `ProjectOffer` / `JobOffer` / `EditorialProduct`, new) subclass a status-only `MarketplaceRepository` with `list_public` / `get_public` (delegating to `public_filters`), **not** `PublishableRepository` — an early version wrongly used the latter, which would have returned nothing for real biz rows.

Non-content resources keep their own criteria, but each in one place: members and organisations on `UserRepository` / `OrganisationRepository` (svcs-registered, resolved via the container); business walls on `BusinessWallRepository` (not svcs-registered — the bw module uses the advanced-alchemy service layer — so the API instantiates it against the request session).

### API adapter

`api_v1/queries.py` resolves the repository (`container.get(...)`, or direct construction for bw) and returns its result. It owns no `where(...)`. The rest of the API (auth, scopes, schemas, HATEOAS, error handling) is unchanged.

### Owner-scoped tier (`/api/v1/me`)

A second tier lets a token-holder reach **their own** private data — the access-parity principle applied. It is gated by a distinct `read:self` scope: `GET /me` (the user's own profile — a fuller `SelfProfileSchema` with their own email/phone/account state, still never `password`/`fs_uniquifier`/clone/IP fields), the newsroom **source** records `GET /me/articles`, `GET /me/press-releases`, `GET /me/enquiry-notices`, and the marketplace `GET /me/missions`, `GET /me/projects`, `GET /me/jobs`, `GET /me/products` (+ `/{id}`). These read the **source** models (wip `Article` / `Communique` / `AvisEnquete`; biz `MissionOffer` / `ProjectOffer` / `JobOffer` / `EditorialProduct`) in **any status incl. drafts**, not the public projections. Ownership lives in a new `OwnedRepository` (`list_owned` / `get_owned`, filtering `owner_id == identity.id AND deleted_at IS NULL`), which the wip repositories subclass and the biz repositories mix in alongside `MarketplaceRepository` — so this tier deliberately **bypasses** the public visibility gate (the owner sees their drafts). `/me` takes no id (the token is the identity); a single-item lookup folds ownership into the query and returns 404 (not 403) for someone else's row, so existence never leaks. The owner sees their own offer's `contact_email`, but never third-party PII (avis recipients in `ContactAvisEnquete`, or applicants/purchasers).

### Write tier (`/api/v1/me`, `write:content`)

The access-parity principle applies symmetrically to writes: an organisation (a press outlet, a PR agency) may **author and publish its own content** through the API to earn the same visibility and monetization it would via the portal — and nothing it could not do in the portal. A distinct `write:content` scope guards, for each of the three content types, `POST /me/{coll}`, `PATCH`/`DELETE /me/{coll}/{id}`, and `POST …/{id}/publish`|`/unpublish` (coll ∈ `press-releases`, `articles`, `events`).

Crucially, the write layer (`writes.py`) **re-uses the domain's authorization and publication logic verbatim**, exactly as the read layer reuses its visibility predicate — so an API publish is indistinguishable from a UI publish. The three types differ only in the reused predicates, mirroring the three WIP rooms:

- **who may author** = the room gate: `user_can_access_comroom` for press releases, `user_can_access_newsroom` (journalists / `PRESS_MEDIA` only) for articles, `user_can_access_eventroom` (+ the `EVENTS` mission when acting as a PR manager) for events — the same predicates the respective `*WipView.before_request` enforce.
- **who may publish for whom** = `can_user_publish_for(user, publisher_id)`: your own organisation, or a client organisation your agency has an active partnership/role with (the "agence de RP" on-behalf case) — for press releases and events. **Articles are own-organisation only**: they have no on-behalf path in the UI, so the API sets `media`/`publisher` to the journalist's own org server-side and accepts no caller-supplied publisher. An unauthorized `publisher_id` is refused — fail closed.
- **ownership** = every mutation targets a row resolved through `OwnedRepository.get_owned`, so a token only ever touches its own content; someone else's id 404s (existence not disclosed), never 403. (`EventRepository` was promoted from `Repository` to `OwnedRepository`, like the other source repos, to power the `/me/events` tier.)
- **publication + monetization** = the source model's `publish()` (state-machine + field validation, `422` on refusal — press releases also reject an active embargo; events also require start/end times with end ≥ start) followed by the existing `*_published` signal — the same path the portal uses, so the public wire/event mirror, the search index, and the rights/monetization snapshot are all produced identically. Monetization is therefore automatic and platform-controlled (consultation paywall priced by genre taxonomy); the API sets no prices and collects no payment account (there is no Stripe Connect). Only `contenu` (the HTML body) is sanitized at the API boundary — matching the model, which sanitizes only that field; `titre`/`chapo` are stored verbatim and rendered escaped (running an HTML sanitizer over plain-text titles would entity-corrupt values like "R&D").

Because authorization and the publication side-effects are delegated, not re-implemented, the write tier cannot grant more than the UI grants, and cannot drift from it. One subtlety surfaced by an adversarial review and fixed: the portal keys its PR-manager mission gate to the *session-selected* Business Wall and forces `publisher_id` to that BW's org, whereas the API takes `publisher_id` as an explicit input. Validating attribution with `can_user_publish_for` alone (which checks only the BWPRi/BWPRe/BW_OWNER role, not the granular mission) would have let a *delegated* PR manager publish for a client org a content type (`PRESS_RELEASE`/`EVENTS`) they were explicitly denied. The fix re-applies the portal's gate against the *target* org's Business Wall (`pr_access.pr_manager_missing_mission`): a delegated PR manager must hold the mission on the target BW; ownership/partnership paths, which the portal doesn't mission-gate, still don't.

A few **deliberate divergences** remain, all strictly *less*-privileged than the portal (never more), chosen to keep the API stateless and predictable:

- **Attribution default** is the caller's own organisation, not the session-selected BW. A stateless token has no meaningful "selected BW"; on-behalf attribution is opt-in via an explicit, authorization-gated `publisher_id` rather than implicit session state.
- **Articles are own-organisation only.** The portal newsroom form lets a journalist pick any active-media org as `media`; the API sets `media`/`publisher` to the journalist's own org and exposes no `media` field. Multi-media targeting (e.g. a freelancer attributing to the outlet they write for) is a scoped follow-up, gated on the same active-media-BW check the portal uses.
- **Drafts carry a null `published_at`** until actually published; the portal stamps a creation-time `published_at` on drafts (a quirk — `status`, not `published_at`, is the source of truth for visibility).

### SDK generation

The spec is served at `/api/v1/openapi.json` and exportable offline via `api_v1.current_openapi_json()`. The client's transport is hand-written and stable; only the drift-prone parts — the collection list and the per-resource typed models — are **generated** from the spec (`sdk/python/generate.py`), keeping the SDK **zero-dependency** (stdlib only). `make api-sdk` exports the live spec and regenerates `aipress24_client/_generated.py`; a unit test regenerates in-memory and asserts the committed file still matches the spec (semantic comparison of collections + model fields, so it's immune to formatting), so a spec change that isn't reflected in the SDK fails CI.

## Consequences

### Positive

- One owner for "publicly visible"; the API cannot drift from the site or search. The write tier reuses the same delegation, so it cannot grant more than the portal grants.
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

**Write parity.** The same principle governs writes: a token may create/publish only content it could create/publish in the portal. Every write reuses the portal's own predicates — the per-room author gate (`user_can_access_comroom` / `user_can_access_newsroom` / `user_can_access_eventroom`, plus the PR-manager mission check), `can_user_publish_for` (which organisation a press release or event may be attributed to; articles are own-org only), and `OwnedRepository.get_owned` (a token mutates only its own rows). Attribution to an unauthorized organisation and mutation of another user's row both fail closed (403 / 404 respectively). Publication runs the domain state machine and signal, so a token cannot bypass the field validation, the embargo (press releases) or date rules (events), or the mirror/index/monetization side-effects that a portal publish applies.

**Enforced (was a v1 gap):** the news schema now serialises the full `content` only when `user_can_read_full(token_user, post)` (author, admin, or a paid/gifted consultation), and `truncate_body(...)` otherwise — reusing the domain check rather than re-implementing it, and matching the site's paywall (including its "show the full body when the paywall is not live" behaviour). A regression test asserts a paywalled body is withheld from a non-entitled token and released to the author. Before this, `ArticleSchema` dumped the full body of every published article, disclosing for-sale content the UI truncates.

**Fixed (was a standing gap):** deleting a newsroom source — article, communique, **or event** (all three publish a public mirror: ArticlePost / PressReleasePost / EventPost) — used to leave the mirror at `status == PUBLIC`, so a soft-deleted item kept being served by the public API, the News portal listing, and the search index. The CBV soft-delete (`_base.py`) now runs a `_post_delete_model` hook; the wire/event CBVs override it to re-emit the existing `*_unpublished` signal, which flips the mirror to DRAFT and de-indexes it — reusing the domain's unpublish path, not a new mechanism. Regression tests assert the mirror leaves `published_filters` after deletion (across all three families, plus the real `delete()` route).

**Fixed (separate pre-existing leak, surfaced by the takedown work):** the News portal *detail* views (`wire/views/item.py`, `events/.../event_detail.py`) previously fetched a post by bare id with **no** visibility gate, serving any DRAFT/unpublished/taken-down post by direct URL. They now use `get_public_obj` (`app/flask/sqla.py`), which 404s a non-`PUBLIC` row for everyone except its owner and admins — access parity with the portal listings, which show only `status == PUBLIC`. Regression tests cover the article and event detail pages. (The public API was never affected here: its detail lookup already applied the `published_filters` gate.)

## Alternatives Considered

- **Option B — Align `queries.py` in place**: keep the API-local query layer but make it match `is_public` semantics. Smallest blast radius, but leaves a second copy of the rule that can re-drift. Rejected: removes the current symptom, not the drift.
- **Option C — Back listings with the wesh search index**: list from the index (the canonical public set) and rehydrate from the DB. Maximal alignment, but the BM25 index is not built for stable resource listing/ordering/id-filtering, and it couples the API to search. Rejected as overkill for v1.
- **Option D — Drop or scope down the API**: ship nothing, or content-only. Rejected: discards working, tested, reviewed code with real integration value.

## Unresolved Questions

- None outstanding. The SDK-generator choice (resolved: a small custom script that keeps the client zero-dependency, over `openapi-python-client`, which would have pulled `httpx`/`attrs` into the generated client) is implemented; see *SDK generation*.

## Future Work

- Broaden the owner-scoped tier further (`/me` now covers own profile, newsroom/eventroom source content, all four marketplace types, and **write** access — create/update/publish/unpublish/delete — for press releases, articles and events): the expert-*received*-avis facet (`ContactAvisEnquete` where `expert_id == identity.id`), and write access to the remaining authored types (`avis d'enquête`) if a use case appears — all reusing `OwnedRepository` + the domain's authorization checks and publish signals. A finer newsroom-tile parity gate (profile_code ∈ `ALLOW_NEWSROOM_ARTICLE` + an active Business Wall) could tighten the article author gate beyond the `PRESS_MEDIA` role if needed; multi-media article targeting (a journalist attributing to a media other than their own org) is likewise a deliberate follow-up.
- Migrate the remaining marketplace views onto the repositories where the query is a plain status-only listing. (The **biz home** listing is migrated, and the biz repositories were corrected to status-only visibility. **Events views are intentionally not migrated**: they are date-range agenda queries — filtering on `start_datetime`/`end_datetime`, not "recently published" — so they legitimately differ from `published_filters` and would be broken by it.)

## References

- `app/modules/search/adapters.py` — `is_public` / `_is_publicly_visible` (canonical per-object predicate)
- `app/models/content/visibility.py` — `published_filters` (query-level predicate)
- ADR 001 — module layering and import discipline (the API module is an import-linter leaf)
- flask-smorest, marshmallow, apispec — the API framework stack
