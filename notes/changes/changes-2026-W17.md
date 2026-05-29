# Changes Week 17, 2026

## PR Agency Publishing — Full Feature Shipped

Card 2025-10-10 closed.

- New `Partnership`-aware backend helpers : `can_user_publish_for`, `get_validated_client_orgs_for_user`, `get_representing_agency_org_ids_for_client`.
- Communiqué + Event publish flows reject unauthorised `publisher_id` ; silent fallback to the user's own org at save time, hard reject with flash at publish time.
- "Publier pour" selector activated on `CommuniqueForm` + `EventForm`, populated with user's own org + validated partnership clients.
- Post cards (Wire + BW tabs) show "Publié par {agence} en tant que contact presse de {client}" when author's org ≠ publisher.
- Cross-BW display : press releases appear on both the emitter BW and the agency BW (factorised OR clause `_press_releases_for_org_clause`).
- Notifications : new `PRPublicationNotificationMail` + template ; client's BW owner notified at each delegated publish (CP + events).

## Matchmaking Avis d'Enquête — Phase 0 MVP

Phase 0 shipped : narrows the notified-expert pool, without changing the journalist UI.

- Thematic pre-filter : intersection of Avis sectors with `profile.secteurs_activite` ; activity window 180 days ; graceful fallback to active pool if < 5 matches.
- Anti-spam : new `AvisNotificationLog` table, cap of 10 notifications / expert / 30 days rolling ; flash warning when some targets are skipped.
- Tunable constants in `avis_matching.py`.

Measurement gathered over 4 weeks before deciding on Phase 1.

## Organisation Refactoring

- New `Organisation.has_bw` property (inverse of `is_auto`) ; `admin/utils`, `swork/organisation` view, `InvitationsView` migrated. Deprecated `unofficial` key removed.
- Deprecated `org.screenshot_url` removed.
- Faker simplified for orgs without type.

## Reactivated Tests

- `test_creates_auto_org_when_no_invitation_match` re-enabled.
- `TestGetOrganisationFamily` re-enabled (uses `bw_type`).

## Invitations / Partnership PR External

- Partnership proposals (external PR Manager) listed on the "invitations d'organisation" page.
- Access button hidden for a Partnership's own initiator.
- Translations : "Organization invitations settings" → "invitations d'organisation" ; Avis status: accepted → accepté, phone → téléphone, etc.

## Stripe MVP — Real Payments Wired In (Behind Flag)

End of the simulation era. Encaissement loop in place, gated behind `STRIPE_LIVE_ENABLED` ; legacy simulation still runs when the flag is off.

**Subscriptions (paid BW)** :

- `payment.html` embeds the Stripe Pricing Table with a mandatory CGV checkbox. Pricing Table posts `client-reference-id=<bw_id>` + `customer-email`, linked to a pre-created DRAFT BW + PENDING Subscription.
- `on_checkout_session_completed` actually activates the BW on `mode=subscription` (was a `pass`). Idempotent via the new unique `Subscription.stripe_checkout_session_id` column.
- `load_pricing_table_id` supports modern `BWType` values (`pr`, `leaders_experts`, `transformers`, `corporate_media`) with legacy fallbacks.
- Cancellation : new "Gérer mon abonnement" dashboard card opens the Stripe Billing Portal (Stripe-hosted). Legacy local "Résilier" button + route defense-masked when the flag is on.

**One-off purchases (3 NEWS buttons)** :

- New `ArticlePurchase` model (enums `PurchaseProduct`, `PurchaseStatus`) + migration. One row per click with unique `stripe_checkout_session_id`.
- 3 article-aside buttons ("Droit de consultation", "Justificatif de publication", "Droits de reproduction") : `href="#"` placeholders replaced with POST forms creating a Stripe Checkout in `mode=payment`. Prices from `STRIPE_PRICE_{CONSULTATION,JUSTIFICATIF,CESSION}` env vars.
- Webhook handler branches on `mode` ; payment branch persists `stripe_payment_intent_id`, `amount_cents`, `currency`, `paid_at` and flips the purchase to `PAID`.
- Downstream effects (paywall unlock, PDF generation, licence) intentionally deferred to dedicated specs.

**Ops & safety net** :

- New `services/stripe/reconciliation.py` walks every local Subscription with a `stripe_subscription_id`, checks status against Stripe, reports drifts (`status_mismatch`, `not_found`).
- New `flask stripe` CLI group : `reconcile` (cron-friendly, non-zero on drift) and `simulate-checkout <bw_id>` (dry-run without Stripe CLI).
- E2E tests cover subscription activation, payment persistence, idempotency on both modes, reconciliation, CLI exit codes.

## Marketplace MVP v0 — Missions Shipped

First real marketplace use case live ; `/biz` Missions tab no longer empty.

- New `MissionOffer` (polymorphic sub-class of `MarketplaceContent`) + `MissionApplication` with unique `(mission_id, owner_id)` constraint (no double candidacy) + cascade delete. Migration `949ffb955454`.
- `POST /biz/missions/new` : title, description, sector, location, budget range, deadline, optional contact email. Euros → cents at save time.
- `GET /biz/missions/<id>` : detail page with inline apply form ; same template for owner view (dashboard CTA + "mark as filled") and candidate view (message textarea / "already applied" banner).
- `GET /biz/missions/<id>/applications` : emitter dashboard with Sélectionner / Refuser buttons.
- `POST /biz/missions/<id>/fill` : flips to `FILLED` and hides the apply form.
- `MissionApplicationMail` + template + `mission_notifications.py` helper : email the emitter on every new candidacy (applicant name, message, profile URL, dashboard URL). Skipped if no recipient email resolvable.
- 14 tests : polymorphic identity, unique constraint, cascade, deposit, candidacy (double-apply rejection, self-apply rejection, filled-mission blocks new candidacies), dashboard, owner-only auth.
- No feature flag : purely additive, no money flow. Rollback : hide the `missions` tab in `_common.TABS`, data stays in DB.

## Marketplace v0.1 + v0.2 — Projects and Jobs

Same day as v0. `MissionApplication` refactored into generic `OfferApplication` with FK to `mkp_content.id` (polymorphic) : one candidature table serves all three offer kinds.

- Shared lifecycle helpers in `biz/views/_offers_common.py` (apply, list, select / reject, mark filled, email notif) ; per-type view files become thin shells.
- `ProjectOffer` (`mkp_project_offer`) : editorial project type with `team_size`, `duration_months`, `project_type`. Home tab `projects` wired with card partial + deposit button.
- `JobOffer` (`mkp_job_offer`) : salaried / fixed-term with `contract_type` (CDI / CDD / STAGE / APPRENTISSAGE / FREELANCE), `full_time`, `remote_ok`, `salary_min/max`, `starting_date`. Candidacy accepts optional `cv_url` (native S3 upload deferred).
- 9 additional e2e tests (5 Projects + 4 Jobs). Marketplace suite : 31 tests.

## Marketplace v0.4 + v0.5 + v0.6 — Moderation, Auto-close, Outcome Notifications

3 shorter sub-releases close the marketplace loop (only matchmaking v0.3 and monetisation V2 remain open).

- **v0.6 — applicant notifications** : new mailers `ApplicationSelectedMail` / `ApplicationRejectedMail` + templates. Select / reject routes email the candidate on status transition ; clicking the same button twice does not re-send. Service renamed `offer_notifications.py` with per-kind URL helpers.
- **v0.5 — auto-close CLI** : `flask biz close-expired` (wire to a nightly cron) flips OPEN offers to CLOSED when their deadline (missions / projects) or starting_date (jobs) is past. In `biz/services/auto_close.py`. Returns per-kind counts.
- **v0.4 — optional moderation** : Dynaconf flag `MARKETPLACE_MODERATION_REQUIRED` (off by default). When ON, new offers default to `PENDING` (hidden from listings, visible to owner only). Admin dashboard `/admin/biz/moderation` with Approve / Reject. Helpers `default_new_offer_status()` + `get_offer_or_404()` so the three offer kinds inherit.
- 13 new e2e tests (3 outcome + 2 auto-close + 8 moderation). Marketplace suite : 44 tests + 1 skipped.

## Cession de Droits MVP v0 — Editor Policy + Per-Post Snapshot + Checkout Guard

The cession buy button can no longer trigger a sale the emitter didn't authorise. Default mode `all_subscribed` keeps existing content sellable.

- New JSON columns : `BusinessWall.rights_sales_policy` (4 modes) + `Post.rights_sales_snapshot`.
- SQLAlchemy `before_update` / `before_insert` hook freezes the emitter BW's policy onto a Post the first time it reaches PUBLIC. Non-retroactive (subsequent edits never overwrite the snapshot).
- `bw_activation/rights_policy.py` exposes `get_policy`, `snapshot_policy_for`, `is_eligible_for_cession`, `emitter_bw_for_post`. Null-snapshot content stays buyable (back-compat).
- Editor settings at `GET/POST /BW/rights-policy` (owner-only) + dashboard card visible only for `media` BW.
- Guard in `POST /wire/<id>/buy/cession` : refuses purchases the snapshot doesn't authorise (no Stripe session created on refusal).
- Cession button hidden on `aside.j2` when the user is clearly ineligible.
- 15 tests (10 unit + 5 e2e). Migration round-trips.

## Article Paywall MVP v0 — Consultation Unlock + Justificatif PDF + Mes Achats

Downstream of the buy buttons. Cession covered separately.

- **Consultation** : `wire/services/article_access.py` with `user_can_read_full` (author, admin, or paid CONSULTATION purchaser) + `truncate_body` (BeautifulSoup HTML-aware truncation, word-boundary cut + ellipsis). Article template shows preview + overlay + buy CTA otherwise. Gated by `STRIPE_LIVE_ENABLED`.
- **Justificatif** : new `ArticlePurchase.pdf_file` (StoredObject S3) + `pdf_signed_url` helper. `wire/services/justificatif.py` renders an HTML template via WeasyPrint, stores the PDF, persists, sends `JustificatifReadyMail` with signed download link. Idempotent. Triggered from Dramatiq actor `app.actors.justificatif.generate_justificatif` enqueued by the webhook on PAID.
- **Mes achats** : `GET /wire/me/purchases` lists PAID purchases with article link or PDF download.
- 16 tests (9 unit + 7 e2e). Suite total : 786 e2e + 482 integration.

## Media Endpoint Refactor — Content-Addressed `/media`

3 copy-pasted `image()` handlers across articles, events, communiqués collapsed into a single authenticated, cache-friendly endpoint. Two latent bugs fixed in passing.

- New `app.modules.media` blueprint with `/media/<storage_name>` : serves bytes by SHA-256 key (already produced by `create_file_object`), reads the S3 backend directly.
- `Image.url` on the three models routes through a shared `media_url(file_object)` helper ; legacy `/wip/articles/<A>/images/<I>` URLs 301 to the new endpoint.
- Response headers : `Cache-Control: private, max-age=31536000, immutable`, ETag, conditional GET. Anonymous requests get a plain `401` (not a Flask-Security redirect) so `<img>` breaks cleanly without logging the user out.
- Incidental fix : public `/wire/article/...` pages used to embed `<img src="/wip/articles/...">` that 401'd for anonymous visitors. Images on the public site now work for logged-out users.
- 11 unit tests with a fake backend.

**Flask-Security Cache-Control patch** : the upstream hook uses dict-style assignment on Werkzeug's `CacheControl` proxy, which serialises as `private=True, no-store=True` — malformed directives on every authenticated response, breaking `/media` caching. Hook replaced in-place with an attribute-setter version (bare tokens). `SECURITY_CACHE_CONTROL` reduced to `{"private": True}` ; session cookies are already HttpOnly + SameSite. Regression test asserts `"private=True"` never appears in `Cache-Control`.

## Avis d'Enquête — Colleague Suggestion Flow (Bug #0061)

The "suggest someone by email" free-text path never notified the suggested person. Redesigned per Erick's instructions.

- Label : "Non, mais je vous suggère une personne **de mon organisation** mieux placée que moi".
- Free-text email replaced by a `<select>` listing active colleagues of the expert's organisation (excluding self + already contacted).
- New FK column `ContactAvisEnquete.suggested_by_user_id` (migration `b8242090d938`) traces the chain.
- `AvisEnqueteService.suggest_colleague(...)` creates a new `ContactAvisEnquete` linked to the suggester, posts an in-app notification, sends `AvisEnqueteNotificationMail` with a "suggérée par <nom>" banner (new `suggested_by_name` field on the mailer), **bypasses the anti-spam cap** (rare, member-triggered).
- When no eligible colleague exists, the option is greyed out with a mailto to `contact@aipress24.com`.
- 9 unit tests + integration test updated.

Follow-ups :

- Refusal reason (`rdv_notes_expert`) persisted on the "non" branch, symmetrical with "non-mais" / "oui".
- Mail to suggested colleague contains an absolute URL (new `_build_opportunity_url` using `SERVER_NAME` ; previous `url_for(...)` returned relative).
- Breadcrumb regression : `_inject_breadcrumbs_to_context` was clobbering manually-set breadcrumbs on routes absent from the nav tree ; short-circuit when `g.nav.breadcrumbs()` is empty.
- `avis_enquete_notification.j2` rebranded (AiPRESS24 wordmark, bold red "i" `#E30613`, bolded labels).

## Bug Batch — #0088, #0050, #0107, #0070

4 tickets closed the same day. Post-mortems in `local-notes/bugs/en-attente-retour/`.

- **#0088** : post-email-change redirected to the change-email form instead of login. Root cause : neither `SECURITY_POST_CHANGE_EMAIL_VIEW` nor `POST_LOGIN_VIEW` set. Fix : `SECURITY_POST_CHANGE_EMAIL_VIEW = "/preferences/"`.
- **#0050** : BW PR Agency activation prompted for number of clients ; product decision was "1 client at activation". New `skip_pricing_input` flag on `BWType.PR` renders a direct link to `pricing_page` (client_count pre-filled to 1). Pricing defaults plumbed for Leaders & Experts / Transformers.
- **#0107** : BW card showed "chef de projet média" for a press redacteur-en-chef. Root cause : `KYCProfile.metier_fonction` fell back to `metiers[0]` when `fonctions_journalisme` was empty. New `metier_fonction_for_bw(bw_type)` with per-BW-type priority. 6 tests.
- **#0070** : Avis d'enquête breadcrumbs degraded to `Work > Avis d'enquête > <title>` with no phase label nor link back. New `_update_phase_breadcrumbs(model, phase)` produces `Work > Avis d'enquête > <title clickable> > <phase>` across 5 sub-routes.

## Taxonomies — Bug #0095

Erick couldn't select "Presse & Médias" when configuring a BW. DB inspection found a phantom `"ORGANISATIONS PRIVÉES "` category (trailing space) holding 7 entries including "Presse & Médias". Stray whitespace in the source ODS.

- Defensive `str.strip()` in `taxonomies._service.create_entry / update_entry` (future bootstraps heal on the fly).
- Alembic data migration `a1c3f8b0e5d2` : `UPDATE tax_taxonomy SET category = trim(category) ...`. Round-trip tested.

## MARKET — Quick Wins (Bug #0073)

Erick's #0073 epic lists ~14 UX improvements for Missions / Projects / Jobs. After review : 3 quick-wins ship now ; the rest is deliberately deferred until real traffic.

- Intro paragraph on each of the 3 offer-creation forms (where listed, how candidacies arrive).
- CSS class `.no-spinner` + `<style>` hiding WebKit / Firefox arrow buttons on budget / salary / team_size / duration_months number inputs.
- Shared macro `poster_card(user)` replaces the free-text `contact_email` field : shows author photo, name, role, organisation, profile link. Email / phone not exposed. Column left in schema for back-compat.

## Upload Diagnostic Endpoint

Minimal `/tests/upload` (`app.modules.tests`) : GET form + POST, bytes drained and discarded, metadata displayed (sent vs received size, Flask `MAX_CONTENT_LENGTH`). Isolates whether photo upload failures (BW gallery, profiles) come from nginx (413 before the app) or Flask. Flask `MAX_CONTENT_LENGTH` is **not** wired — so failures at MB-sized payloads are almost certainly nginx.

## BW — Multi-Select and PR Stripe Form (WIP, JD)

- New helpers `get_manageable_business_walls_for_user()`, `get_selected_business_wall_for_user()`.
- Selector page when a user manages several BW (BWMi, BWMe, owner).
- Current-managed-BW name in the UI.
- Stripe form for PR Agency (WIP) ; `count_pr_bw_customers()` helper + unit test.
- `stripe/webhook.py` refactored (imports, type hints) ; Stripe drift fixed for BW created before Stripe was wired.
- `is_organisation_an_agency()` : NPE when org has no BW — warn gated inside `bw is not None`.

## Community Role Regression — RP Saw Newsroom

Critical regression in staging : a user with KYC profile "Relations presse" could see and enter the Newsroom, reserved to journalists.

- **Root cause** : `append_user_role_from_community` (in `modules/kyc/community_role.py`) only added the target role without removing previous community roles. Any user who changed community ended up with the union of both menus + ACLs. The legacy test `assert len(user.roles) == 2` was locking in the exact symptom.
- **DB impact (prod scan)** : 4 users with multiple community roles — Eliane (PR_CS_IND + stale PRESS_MEDIA), Erick (PM_DIR + stale EXPERT), JD (XP_DIR_ANY + PRESS_MEDIA), Denise (faker, EXPERT + TRANSFORMER).
- **Fix** : `set_user_role_from_community` drops all other community roles before adding the target. Orthogonal roles (MANAGER, ADMIN, LEADER…) preserved. Legacy name kept as alias — the 3 call sites pick up the new semantics automatically.
- **Migration** `d3f7a49c20b1` : PostgreSQL `DELETE ... USING` removes, per user, community roles that don't match their `kyc_profile.profile_community`. Round-trip tested. Post-migration : 0 multi-community users, 0 orphans.
- 5 new test cases replace the buggy legacy one : initial assignment, replacement (Eliane), idempotence, orthogonal-role preservation, alias.

Cross-check : for each of the 5 communities, the Work menu visibility matches the expected community with no cross-leak (PRESS_MEDIA sees Newsroom not Com'room ; the other 4 the inverse).

## Breadcrumb Fix on Image Pages (Bug #0085)

Same family as #0070 but on the articles / events / communiqués image-management pages : breadcrumb was a flat `Work > List > <title>` with no link back and no phase label.

- Shared `update_phase_breadcrumbs(model, phase)` extracted on `BaseWipView`.
- Wired into `ArticlesWipView.images()`, `EventsWipView.images()`, `CommuniquesWipView.images()`.
- `AvisEnqueteWipView._update_phase_breadcrumbs` (fix #0070) becomes a thin wrapper — no duplication.

## In-App Notifications Surfaced in the Header

The notification service was already producing DB rows but no UI surfaced them — the header bell had been commented out during a previous menu refactor.

- Bell dropdown re-enabled in `fragments/header-menu-dropdowns.j2` with unread-count badge (`get_unread_notification_count()` context processor).
- New `app.modules.notifications` blueprint : `POST /notifications/mark-all-read` + `POST /notifications/<id>/read`. Login-gated ; open-redirect protection via `urllib.parse.urlparse` on `next`.
- Typed service methods on `NotificationRepository` : `get_notifications`, `get_unread_count`, `mark_all_as_read`, `mark_as_read`.
- `dropdown-notifications.j2` rewritten : each row is a `<form>` POST that marks read before redirecting ; blue dot for unread, humanised timestamp, "Tout marquer comme lu" footer, empty state.
- Composite index `ix_not_notifications_receiver_read_ts(receiver_id, is_read, timestamp)` (migration `e5b2a97f3c14`) — avoids a full scan on every authenticated render.
- 5 unit tests covering scoping to receiver + mark transitions.

## Admin `/show_user` Improvements (JD)

- Display of all available role / auth / invitation information.
- BW name + type shown when the user's org has a BW.
- Explicit message when no portrait photo available.
- Fix : "carte presse" image actually displayed (was showing the portrait).

## Misc Fixes (JD)

- SWORK organisation list search now matches both organisation name and BW name.
- Long snowflake IDs no longer corrupted by JS integer-size limit.
- PR unauthorised publication no longer silently ignored (subtle bug where a Communiqué draft written before authorisation behaved incorrectly at publish time).

## Infrastructure & Docs

- Nix flake support removed.
- Typechecking fixes (`ty`) ; `# ty:ignore` pragma harmonised alongside `# type: ignore`.
- POC updated ; dependencies refreshed.
- New product specs (FR) in `local-notes/specs/` : Stripe integration (full vision + MVP v0), cession de droits, article paywall, PR agency publishing, matchmaking, marketplace, items mineurs.
- `local-notes/plans/integration-stripe-mvp.md` : detailed Stripe MVP plan (files, day-by-day, pré-go-live check-list).
- `local-notes/stripe-mvp-deployment.md` : operational runbook for EH (Stripe dashboard clicks, env vars, CGV, phased rollout, FAQ).
- `local-notes/plans-2026.md` rewritten MVP-focused ; new `local-notes/plan-post-mvp.md`.
- New weekly notes W15 / W16 / W17 in `local-notes/weekly/`.
