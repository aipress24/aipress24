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

## Infrastructure

- Nix flake support removed.
- Typechecking fixes (`ty`), with `# ty:ignore` pragma harmonised
  alongside existing `# type: ignore`.
- POC updated.
- Dependencies refreshed.

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
- Weekly notes W15 / W16 / W17 added in `local-notes/weekly/`.
- Open-todos backlog reviewed against code state.
