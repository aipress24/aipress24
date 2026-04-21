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

## Infrastructure

- Nix flake support removed.
- Typechecking fixes (`ty`), with `# ty:ignore` pragma harmonised
  alongside existing `# type: ignore`.
- POC updated.
- Dependencies refreshed.

## Documentation

- New product specs (FR) in `local-notes/specs/`: Stripe integration,
  cession de droits, article paywall, PR agency publishing,
  matchmaking, marketplace, items mineurs.
- `local-notes/plans-2026.md` updated (pending work reorganised by
  priority, delivered H1 2026 snapshot).
- Weekly notes W15 / W16 / W17 added in `local-notes/weekly/`.
- Open-todos backlog reviewed against code state.
