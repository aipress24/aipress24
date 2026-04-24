# Changes Week 17, 2026

## PR Agency Publishing — Full Feature Shipped

Feature delivered end-to-end, card 2025-10-10 closed.

**Backend authorization**

- New `Partnership`-aware helpers (`can_user_publish_for`,
  `get_validated_client_orgs_for_user`,
  `get_representing_agency_org_ids_for_client`).
- Communiqué and Event publish flows reject unauthorized
  `publisher_id`; silent fallback to user's own org at save time,
  hard reject with flash message at publish time.

**UI**

- "Publier pour" selector activated on `CommuniqueForm` and
  `EventForm`, populated with the user's organisation + validated
  partnership clients.
- Post cards (Wire + BW tabs) now show "Publié par {agence} en tant
  que contact presse de {client}" when the author's org differs from
  the publisher.

**Cross-BW display**

- Press releases appear on both the emitter BW and the representing
  agency BW (factorised OR clause `_press_releases_for_org_clause`).

**Notifications**

- New `PRPublicationNotificationMail` + e-mail template.
- Client's BW owner is notified at each delegated publish (both
  communiqués and events).

## Matchmaking Avis d'Enquête — Phase 0 MVP

Phase 0 of the matchmaking spec shipped — narrows the notified-expert
pool without touching the journalist UI.

- Thematic pre-filter: intersection of Avis sectors with
  `profile.secteurs_activite`, activity window 180 days, graceful
  fallback to the active pool if fewer than 5 matches.
- Anti-spam: new `AvisNotificationLog` table, cap at 10 notifications
  per expert over a 30-day rolling window; flash warning when some
  targets are skipped.
- Tunable constants (`ACTIVITY_LOOKBACK_DAYS`, `NOTIFICATION_CAP`,
  etc.) in `avis_matching.py`.

Measurement to be gathered over 4 weeks before deciding on Phase 1.

## Organisation Refactoring

- New `Organisation.has_bw` property (inverse of `is_auto`, more
  explicit); `admin/utils`, `swork/organisation` view, `InvitationsView`
  context migrated to use it. Deprecated `unofficial` key removed.
- Deprecated `org.screenshot_url` attribute removed.
- Faker scripts simplified for organisations without type.

## Reactivated Tests

- `test_creates_auto_org_when_no_invitation_match` re-enabled.
- `TestGetOrganisationFamily` re-enabled; `get_organisation_family()`
  updated to use `bw_type`.

## Invitations / Partnership PR External

- Partnership proposals (external PR Manager) now listed on the
  "invitations d'organisation" page.
- Access button hidden for a Partnership's own initiator (their own
  BW).
- Breadcrumb translation: "Organization invitations settings" →
  "invitations d'organisation".
- Avis d'Enquête status translations: accepted → accepté, phone →
  téléphone, etc.

## Stripe MVP — Real Payments Wired In (behind flag)

End of the simulation era. The whole encaissement loop is now in place
and gated behind `STRIPE_LIVE_ENABLED`; the legacy simulation still
runs when the flag is off.

**Subscriptions (BW payants)**

- `payment.html` embeds the Stripe Pricing Table with a mandatory CGV
  checkbox. The Pricing Table posts `client-reference-id=<bw_id>` +
  `customer-email`, which we link to a pre-created DRAFT BW +
  PENDING Subscription.
- `on_checkout_session_completed` now actually activates the BW on
  `mode=subscription` (was a `pass`). Idempotent via the new unique
  `Subscription.stripe_checkout_session_id` column.
- `load_pricing_table_id` supports modern `BWType` values (`pr`,
  `leaders_experts`, `transformers`, `corporate_media`) with legacy
  fallbacks.
- Cancellation : new "Gérer mon abonnement" dashboard card opens the
  Stripe Billing Portal (resiliation, CB, invoices, all hosted by
  Stripe). The legacy local "Résilier" button + route are
  defense-masked when the flag is on to avoid Stripe/local drift.

**One-off purchases (3 NEWS buttons)**

- New `ArticlePurchase` model (enums `PurchaseProduct`,
  `PurchaseStatus`) + migration. One row per click with unique
  `stripe_checkout_session_id`.
- Three article-aside buttons ("Droit de consultation",
  "Justificatif de publication", "Droits de reproduction") moved from
  `href="#"` placeholders to POST forms that create a Stripe Checkout
  session in `mode=payment`. Prices resolved from
  `STRIPE_PRICE_{CONSULTATION,JUSTIFICATIF,CESSION}` env vars.
- The webhook handler branches on `mode`; the payment branch persists
  `stripe_payment_intent_id`, `amount_cents`, `currency`, `paid_at`
  and flips the purchase to `PAID`.
- Downstream effects (paywall unlock, PDF generation, licence issuance)
  intentionally deferred to the `article-paywall.md` and
  `cession-droits.md` specs.

**Ops & safety net**

- New `services/stripe/reconciliation.py` walks every local
  Subscription with a `stripe_subscription_id`, checks the status
  against Stripe, and reports drifts (`status_mismatch`, `not_found`).
- New `flask stripe` CLI group : `reconcile` (cron-friendly, exits
  non-zero on drift) and `simulate-checkout <bw_id>` (dry-run without
  Stripe CLI).
- E2E tests cover subscription activation, payment persistence,
  idempotency on both modes, reconciliation paths, and CLI exit codes.

## Marketplace MVP v0 — Missions shipped

First real marketplace use case goes live. The `/biz` Missions tab is
no longer empty.

- New `MissionOffer` (polymorphic sub-class of `MarketplaceContent`)
  and `MissionApplication` models, with unique `(mission_id, owner_id)`
  constraint to prevent double candidacy and cascade delete.
- New migration `949ffb955454_biz_missions_mvp`.
- `POST /biz/missions/new` form (title, description, sector, location,
  budget range, deadline, optional contact e-mail). Euros converted to
  cents at save time.
- `GET /biz/missions/<id>` detail page with inline apply form; same
  template handles the owner view (dashboard CTA + "mark as filled"
  button) and the candidate view (message textarea / "already applied"
  banner).
- `GET /biz/missions/<id>/applications` emitter dashboard listing all
  candidacies with Sélectionner / Refuser buttons.
- `POST /biz/missions/<id>/fill` flips `MissionStatus` to `FILLED` and
  hides the apply form on subsequent visits.
- `MissionApplicationMail` + template +
  `biz/services/mission_notifications.py` helper: e-mail the emitter
  with applicant name, message, profile URL, and dashboard URL on
  every new candidacy. Silently skipped when no recipient e-mail can
  be resolved.
- `biz/views/home.py` now wires the `missions` tab; the listing uses a
  dedicated `pages/missions/_card.j2` partial that branches on
  polymorphic type.
- 14 tests cover model invariants (polymorphic identity, unique
  constraint, cascade), the deposit flow, the candidacy flow
  (including double-apply rejection, self-apply rejection, filled
  mission blocking new candidacies), the dashboard, and the owner-only
  authorization checks.
- No feature flag: the feature is purely additive and doesn't touch
  money, so it rolls out on merge. Rollback path: hide the `missions`
  tab in `_common.TABS` — data stays in DB.
- Post-v0 (Projets, Emplois, matchmaking, modération, auto-close,
  candidate notification) remains in the spec as deferred phases; see
  `local-notes/plans/marketplace-mvp.md` § 8.

## Marketplace v0.1 + v0.2 — Projects and Jobs shipped

Same day as the v0, the next two sub-releases ship.

- `MissionApplication` refactored into generic `OfferApplication`
  with FK to `mkp_content.id` (polymorphic). One candidature table
  serves all three offer kinds; migration round-trips cleanly.
- Shared helpers in `biz/views/_offers_common.py` drive the common
  lifecycle (apply, list, select/reject, mark filled, e-mail notif);
  per-type view files are thin coquilles.
- `ProjectOffer` (`mkp_project_offer`) — editorial project type with
  `team_size`, `duration_months`, `project_type`. Home tab
  `projects` wired with dedicated card partial and deposit button.
- `JobOffer` (`mkp_job_offer`) — salaried/fixed-term positions with
  `contract_type` (CDI/CDD/STAGE/APPRENTISSAGE/FREELANCE),
  `full_time`, `remote_ok`, `salary_min/max`, `starting_date`.
  Candidacy form accepts an optional `cv_url`; native S3 upload
  deferred to v0.2.x.
- 9 additional e2e tests (5 Projects + 4 Jobs). Marketplace suite
  total: 31 tests across missions + projects + jobs + 1 skipped
  cascade assertion.

## Marketplace v0.4 + v0.5 + v0.6 — Moderation, auto-close, outcome notifications

Three shorter-but-structural sub-releases complete the marketplace
loop (only matchmaking v0.3 and monetization V2 remain open).

- **v0.6 — applicant notifications**: new mailers
  `ApplicationSelectedMail` and `ApplicationRejectedMail` + HTML
  templates. The select/reject routes e-mail the candidate on
  status transition; clicking the same button twice does not
  re-send. The notifications service is renamed
  `offer_notifications.py` and gains per-kind URL helpers
  (missions / projects / jobs).
- **v0.5 — auto-close CLI**: `flask biz close-expired` (wire it to
  a nightly cron) flips OPEN offers to CLOSED when their deadline
  (missions/projects) or starting_date (jobs) is past. Lives in
  `biz/services/auto_close.py`, returns per-kind counts for log
  output. Zero external dependency.
- **v0.4 — optional moderation**: new Dynaconf flag
  `MARKETPLACE_MODERATION_REQUIRED` (off by default, no behaviour
  change). When ON, new offers default to `PENDING` (hidden from
  listings, visible to owner only). Admin dashboard at
  `/admin/biz/moderation` lists the queue and offers
  Approve/Reject buttons. Logic sits in `default_new_offer_status()`
  and `get_offer_or_404()` helpers so the three offer kinds pick it
  up for free.
- Tests: 13 new e2e (3 outcome + 2 auto-close + 8 moderation).
  Marketplace suite now 44 tests + 1 skipped cascade. No regression
  on the 774 e2e and 463 integration tests.

## Cession de droits MVP v0 — Editor policy + per-Post snapshot + checkout guard

The W17 cession buy button can no longer trigger a sale that the
emitter didn't authorise. Mode défaut `all_subscribed` keeps
existing content sellable.

- New JSON columns: `BusinessWall.rights_sales_policy` (4 modes)
  and `Post.rights_sales_snapshot`.
- SQLAlchemy `before_update`/`before_insert` hook freezes the
  emitter BW's policy onto a Post the first time it reaches PUBLIC.
  Non-retroactive: subsequent edits never overwrite the snapshot.
- `bw_activation/rights_policy.py` exposes `get_policy`,
  `snapshot_policy_for`, `is_eligible_for_cession`,
  `emitter_bw_for_post`. Null-snapshot content stays buyable
  (back-compat).
- Editor settings page at `GET/POST /BW/rights-policy`
  (owner-only) + dashboard card visible only for BW of type
  `media`.
- Guard in `POST /wire/<id>/buy/cession`: refuses purchases the
  snapshot doesn't authorise (no Stripe session created on refusal).
- The cession button is hidden on `aside.j2` when the connected
  user is clearly ineligible.
- 15 tests (10 unit + 5 e2e). Migration round-trips.

## Article paywall MVP v0 — Consultation unlock + justificatif PDF + Mes achats

The downstream effect of the W17 buy buttons. The cession button
is covered by the cession-droits MVP above.

- **Consultation**: `wire/services/article_access.py` with
  `user_can_read_full` (author, admin, or paid CONSULTATION
  purchaser) and `truncate_body` (BeautifulSoup HTML-aware
  truncation with word-boundary cut + ellipsis). Article template
  shows preview + overlay + buy CTA otherwise. Gated by
  `STRIPE_LIVE_ENABLED` so the feature is invisible until go-live.
- **Justificatif**: new `ArticlePurchase.pdf_file` (StoredObject
  S3) + `pdf_signed_url` helper. Service
  `wire/services/justificatif.py` renders an HTML template via
  WeasyPrint, stores the PDF, persists, and sends a new
  `JustificatifReadyMail` with the signed download link.
  Idempotent. Triggered from a Dramatiq actor
  (`app.actors.justificatif.generate_justificatif`) enqueued by
  the webhook on PAID.
- **Mes achats**: `GET /wire/me/purchases` lists the user's PAID
  purchases with article link or PDF download.
- 16 tests (9 unit + 7 e2e). Suite total unchanged: 786 e2e + 482
  integration.

## Media Endpoint Refactor — Content-Addressed `/media`

Three copy-pasted `image()` handlers across articles, events and
communiqués collapsed into a single authenticated, cache-friendly
endpoint, while two latent bugs are fixed in passing.

- New `app.modules.media` blueprint with a single DB-free handler
  `/media/<storage_name>` that serves bytes by SHA-256 key (already
  produced by `create_file_object`), reading the S3 backend directly
  via `storages.get_backend("s3").get_content(...)`.
- `Image.url` on the three models now routes through a shared
  `media_url(file_object)` helper; the legacy
  `/wip/articles/<A>/images/<I>` URLs 301 to the new endpoint.
- Response headers:
  `Cache-Control: private, max-age=31536000, immutable`, ETag,
  conditional GET. Anonymous requests get a plain `401` (not a
  Flask-Security redirect) so `<img>` breaks cleanly without
  logging the user out.
- Incidental fix: public `/wire/article/...` pages used to embed
  `<img src="/wip/articles/...">` that `401` for anonymous
  visitors. Images on the public site now work for logged-out users
  (still authenticated, but the redirect loop is gone).
- 11 unit tests using a fake backend.

**Flask-Security Cache-Control patch**

- Flask-Security-Too's `add_cache_control` hook uses dict-style
  assignment on Werkzeug's `CacheControl` proxy
  (`resp.cache_control["private"] = True`), which serialises as
  `private=True, no-store=True` — malformed directives on every
  authenticated response, breaking `/media` caching too.
- Hook replaced in-place in `app.after_request_funcs[None]` with an
  attribute-setter version (bare tokens). `SECURITY_CACHE_CONTROL`
  reduced to `{"private": True}` — session cookies are already
  HttpOnly + SameSite, no need for `no-store`.
- Regression test asserts `"private=True"` never appears in
  `Cache-Control`.

## Avis d'Enquête — Colleague Suggestion Flow (Bug #0061)

The free-text "suggest someone by email" path never notified the
suggested person. Redesigned per Erick's instructions.

- Label changed to "Non, mais je vous suggère une personne **de mon
  organisation** mieux placée que moi".
- Free-text email input replaced with a `<select>` listing active
  colleagues of the expert's organisation (excluding self, excluding
  those already contacted for this Avis).
- New FK column `ContactAvisEnquete.suggested_by_user_id`
  (migration `b8242090d938`) traces the chain.
- `AvisEnqueteService.suggest_colleague(...)` creates a new
  `ContactAvisEnquete` linked to the suggester, posts an in-app
  notification (Opportunités Média), sends
  `AvisEnqueteNotificationMail` with a new "suggérée par <nom>"
  banner (new `suggested_by_name` field on the mailer),
  **bypasses the anti-spam cap** (rare, member-triggered).
- When no eligible colleague exists, the option is greyed out with
  a mailto to `contact@aipress24.com`.
- 9 unit tests + existing integration test updated.

Follow-up fixes (JD, same day and day after):

- Persist a refusal reason (`rdv_notes_expert`) on the "non"
  branch, symmetrical with "non-mais" and "oui".
- Mail sent to the suggested colleague now contains an absolute URL
  (dedicated `_build_opportunity_url` using `SERVER_NAME`); the
  previous `url_for(...)` returned a relative path.
- Breadcrumb regression: `_inject_breadcrumbs_to_context` was
  clobbering manually-set breadcrumbs on routes absent from the
  nav tree; short-circuit when `g.nav.breadcrumbs()` is empty.

Rebranded `avis_enquete_notification.j2` as a side task: AiPRESS24
wordmark (bold, red "i" `#E30613`), bolded labels, intro and
instruction paragraphs.

## Bug Batch — #0088, #0050, #0107, #0070

Four tickets closed the same day. Ticket files in
`local-notes/bugs/en-attente-retour/` hold the detailed
post-mortems.

- **#0088** — post-email-change redirected to the change-email
  form instead of the login page. Root cause: neither
  `SECURITY_POST_CHANGE_EMAIL_VIEW` nor `POST_LOGIN_VIEW` set. Fix:
  `SECURITY_POST_CHANGE_EMAIL_VIEW = "/preferences/"` in
  `flask/main.py`.
- **#0050** — BW PR Agency activation prompted for number of
  clients though the product decision was "1 client at
  activation". New `skip_pricing_input` flag on `BWType.PR` renders
  a direct link to `pricing_page` (client_count pre-filled to 1).
  Pricing defaults also plumbed for Leaders & Experts / Transformers
  to avoid re-entry.
- **#0107** — BW card showed "chef de projet média" for a press
  redacteur-en-chef. Root cause: `KYCProfile.metier_fonction` fell
  back to `metiers[0]` when `fonctions_journalisme` was empty.
  New `metier_fonction_for_bw(bw_type)` with a priority source
  table per BW type — no misleading fallback. 6 tests.
- **#0070** — Avis d'enquête breadcrumbs degraded to
  `Work > Avis d'enquête > <title>` with no phase label nor link
  back. New `_update_phase_breadcrumbs(model, phase)` produces
  `Work > Avis d'enquête > <title clickable> > <phase>` across
  5 sub-routes.

## Taxonomies — Bug #0095

Erick couldn't select "Presse & Médias" when configuring a BW.
DB inspection found a phantom `"ORGANISATIONS PRIVÉES "` category
(trailing space) sequestering 7 entries including "Presse &
Médias". Caused by stray whitespace in the source ODS.

- Defensive `str.strip()` in
  `app.services.taxonomies._service.create_entry` /
  `update_entry` — future bootstraps heal on the fly.
- Alembic data migration `a1c3f8b0e5d2`:
  `UPDATE tax_taxonomy SET category = trim(category) ...` for
  existing rows. Round-trip tested.

## MARKET — Quick Wins (Bug #0073)

Erick's `0073` epic lists ~14 UX improvements for Missions /
Projects / Jobs. Drastic prioritisation after review: three
quick-wins that fix objective friction ship now; the rest is
**deliberately deferred** until we have real traffic on MARKET.

- Intro paragraph on each of the three offer-creation forms
  (says where the offer will be listed and how candidacies reach
  the emitter).
- CSS class `.no-spinner` + `<style>` hiding WebKit/Firefox arrow
  buttons on budget / salary / team_size / duration_months number
  inputs.
- Shared macro `poster_card(user)` replacing the free-text
  `contact_email` field: shows author photo, name, role,
  organisation, profile link. Email/phone not exposed. Column
  left in the schema for back-compat.
- Deferred: 14-select targeting on the three sub-modules,
  reusing the Avis-d'enquête targeting module in Missions,
  Commande/Dates-clés module, transversal refactor.

## Upload Diagnostic Endpoint

Minimal `/tests/upload` (`app.modules.tests`): GET form + POST on
the same URL, bytes drained and discarded, metadata displayed
(sent vs received size, Flask `MAX_CONTENT_LENGTH`). Isolates
whether photo upload failures (BW gallery, profiles) come from
nginx (413 before the app) or Flask. Flask's
`MAX_CONTENT_LENGTH` is **not** wired — if a photo of X MB fails
it's almost certainly nginx.

## BW — Multi-Select and PR Stripe Form (WIP, JD)

- Helpers `get_manageable_business_walls_for_user()` and
  `get_selected_business_wall_for_user()`.
- Selector page when a user manages several BW (BWMi, BWMe,
  owner).
- Current-managed-BW name now displayed in the UI.
- Stripe form for PR Agency (WIP).
- Helper `count_pr_bw_customers()` + unit test.
- Refactor of `stripe/webhook.py` (imports, type hints).
- Fix Stripe drift for BW created before Stripe was wired.
- `is_organisation_an_agency()`: NPE when org has no BW —
  warn call now gated inside `bw is not None`.

## Community Role Regression — RP Saw Newsroom

Critical regression found in staging: a user with KYC profile
"Relations presse" (RP) could see and enter the Newsroom,
reserved to journalists (PRESS_MEDIA).

**Root cause**: `append_user_role_from_community` (in
`modules/kyc/community_role.py`) only *added* the target role
without removing previous community roles. Any user who changed
community (e.g. journalist → relations presse) ended up with the
union of both menus and ACLs. The legacy test
`assert len(user.roles) == 2` was locking in the exact symptom.

**DB impact (prod scan)**: 4 users with multiple community roles,
including Eliane (PR_CS_IND + stale PRESS_MEDIA), Erick (PM_DIR +
stale EXPERT), JD (XP_DIR_ANY + PRESS_MEDIA), and Denise (faker,
EXPERT + TRANSFORMER).

**Fix**:

- `set_user_role_from_community` rewrites: drops all other
  community roles before adding the target. Orthogonal roles
  (MANAGER, ADMIN, LEADER…) preserved.
- Legacy name `append_user_role_from_community` kept as alias —
  the 3 call sites (kyc/views.py, faker/users.py) pick up the new
  semantics automatically.
- Migration `d3f7a49c20b1`: PostgreSQL `DELETE ... USING` that
  removes, for each user, community roles that don't match their
  `kyc_profile.profile_community`. Round-trip tested. Post-migration:
  0 multi-community users, 0 orphans.
- Tests: 5 new cases replace the buggy legacy test — initial
  assignment, replacement (Eliane), idempotence, orthogonal-role
  preservation, alias.

**Cross-check**: for each of the 5 communities, the Work menu
visibility matches the expected community with no cross-leak
(PRESS_MEDIA sees Newsroom and not Com'room; the other 4 see
Com'room and not Newsroom).

## Breadcrumb Fix on Image Pages (Bug #0085)

Same family as #0070 but on the articles / events / communiqués
image-management pages (`.../images/`): breadcrumb was a flat
`Work > List > <title>` with no link back and no phase label —
journalists uploading photos had to walk all the way back to the
dashboard to reach the "⋯" menu.

- Shared `update_phase_breadcrumbs(model, phase)` extracted on
  `BaseWipView`, producing
  `Work > <label_list> > <title clickable> > <phase>`.
- Wired into `ArticlesWipView.images()`,
  `EventsWipView.images()`, `CommuniquesWipView.images()`.
- `AvisEnqueteWipView._update_phase_breadcrumbs` (fix #0070)
  becomes a thin wrapper — no duplication.

## In-App Notifications Surfaced in the Header

The notification service was already producing DB rows (Avis
d'enquête, Partnership, …) but no UI surface exposed them — the
header bell had been commented out during a previous menu
refactor.

- Bell dropdown re-enabled in
  `fragments/header-menu-dropdowns.j2` with an unread-count
  badge (`get_unread_notification_count()` context processor).
- New `app.modules.notifications` blueprint:
  `POST /notifications/mark-all-read` and
  `POST /notifications/<id>/read`. Login-gated; open-redirect
  protection via `urllib.parse.urlparse` on `next`.
- Typed service methods on `NotificationRepository`:
  `get_notifications(user, max)`, `get_unread_count(user)`,
  `mark_all_as_read(user)`, `mark_as_read(id, user)`.
- `dropdown-notifications.j2` rewritten: each row is a `<form>`
  POST that marks as read before redirecting to the target URL;
  blue dot for unread, humanized timestamp, "Tout marquer comme
  lu" footer, empty state.
- Composite index
  `ix_not_notifications_receiver_read_ts (receiver_id, is_read,
  timestamp)` (migration `e5b2a97f3c14`) — avoids a full scan on
  `not_notifications` for every authenticated render.
- 5 new unit tests covering scoping to receiver + mark
  transitions.

## Organisation Refactoring (JD)

- `Organisation.has_bw` property (inverse of `is_auto`, more
  explicit); `admin/utils`, `swork/organisation` view,
  `InvitationsView` context migrated. Deprecated `unofficial` key
  removed.
- Deprecated `org.screenshot_url` removed.
- Faker scripts simplified for organisations without type.

## Reactivated Tests (JD)

- `test_creates_auto_org_when_no_invitation_match` re-enabled.
- `TestGetOrganisationFamily` re-enabled;
  `get_organisation_family()` updated to use `bw_type`.

## Invitations / Partnership PR External (JD)

- Partnership proposals (external PR Manager) listed on the
  "invitations d'organisation" page.
- Access button hidden for a Partnership's own initiator.
- Breadcrumb translation: "Organization invitations settings" →
  "invitations d'organisation".
- Avis d'Enquête status translations: accepted → accepté, phone →
  téléphone, etc.

## Admin `/show_user` Improvements (JD)

- Display of all available role / auth / invitation information.
- Show BW name and type if the user's org has a BW.
- Explicit message when no portrait photo available.
- Fix: actually display the "carte presse" image rather than the
  portrait.

## Misc Fixes (JD)

- SWORK organisation list search now matches both organisation
  name and BW name (for cases where they differ).
- Long integer (snowflake IDs) no longer corrupted by JS integer
  size limit.
- PR unauthorised publication: no longer silently ignored (fixed
  a subtle bug where a Communiqué draft written before actual
  authorisation of the PR agent behaved incorrectly at publish
  time).

## Infrastructure

- Nix flake support removed.
- Typechecking fixes (`ty`), with `# ty:ignore` pragma harmonised
  alongside existing `# type: ignore`.
- POC updated.
- Dependencies refreshed.
- New weekly notes W15 / W16 / W17 in `local-notes/weekly/`.
- `local-notes/plans-2026.md` rewritten MVP-focused (executive
  summary + itemized list, ship-blockers, bug-fix batch, go/no-go
  checks, nice-to-haves).
- New `local-notes/plan-post-mvp.md` (executive summary +
  measurement-driven iterations for Avis matchmaking / Marketplace
  / paywall / cession, monetisation pointers, infrastructure
  follow-ups, technical debt).

## Documentation

- New product specs (FR) in `local-notes/specs/`: Stripe integration
  (full vision + MVP v0), cession de droits, article paywall, PR
  agency publishing, matchmaking, marketplace, items mineurs.
- `local-notes/plans/integration-stripe-mvp.md` : detailed technical
  plan for the Stripe MVP (files, day-by-day breakdown,
  check-list pré-go-live).
- `local-notes/stripe-mvp-deployment.md` : operational runbook for EH
  (Stripe dashboard clicks, env vars, CGV, phased rollout, FAQ).
- `local-notes/plans-2026.md` updated (pending work reorganised by
  priority, delivered H1 2026 snapshot).
- Open-todos backlog reviewed against code state.
