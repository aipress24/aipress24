# Changes Week 22, 2026

A 5-day week (~70 commits) in three movements. May 25-26 : deep Trello bug-fix campaign + a first batch of PR Manager enablement for Newsroom / Comroom / Eventroom (JD). May 28 : partial revert of the Newsroom share after an Erick bug report. May 29 : end-of-week cleanup — `RoleEnum.MANAGER` / `User.is_manager` deprecation, multi-layered BW-Owner safety net at user / org removal, start on Stripe subscription product retrieval. Stripe Dashboard doc finalised for EH. Test-infra debt repaid (UNIQUE on roles join table, dynamic discovery in the e2e lifecycle).

## PR Manager Enablement — Newsroom / Comroom / Eventroom (May 25)

A coordinated change set (JD) that lets a PR Manager of a partner agency publish content on behalf of a client BW, gated by the fine-grained `PermissionType` configured on that client BW.

- **`publisher_id` lifted to `NewsroomCommonMixin`** : Article, Sujet, Commande, Avis d'Enquête now share a single `@declared_attr`-defined column. Migration adds the column to `nrm_*` tables ; a follow-up fixed a side-effect dropping `evt_event_post.publisher_id` by accident.
- Newsroom / Comroom / Eventroom access opened to PR Managers via new helpers `user_can_access_eventroom`, `user_has_mission`, etc. Check rendered at navigation + per-action gate.
- Per-type `PermissionType` checks shipped, one per content type (PRESS_RELEASE, EVENTS, MISSIONS, PROJECTS, INTERNSHIPS+APPRENTICESHIPS+DOCTORAL). Permission read from the client BW at each publish, not from the agency's role globally.
- Publisher name in cards : when a PR Manager publishes for a client, the card shows the client's name (same dual-clause model as `_press_releases_for_org_clause`).
- `DASHBOARD_ACCESS_ROLES` tightened : BWPRI / BWPRE removed (per #0157 / #0139 — these roles are not BW managers).

7 dedicated `test_user` fixtures added for the new permission matrix.

## Newsroom Revert (May 28)

3 days after shipping, Erick reported : "Alfred Delarue, directeur de la PR Agency Fake-Garden RP, dispose dans son espace WORK du module NEWSROOM qui doit rester exclusivement réservé aux journalistes." Even when a PR Manager selects a client BW where they hold BWPRi / BWPRe and is correctly identified by `user_is_acting_as_pr_manager`, the Newsroom shouldn't be visible to them. The Comroom / Eventroom half is fine ; the Newsroom half was wrong.

JD reverted partially the same day :

- `user_can_access_newsroom` reduced to `has_role(user, [RoleEnum.PRESS_MEDIA])`. `_allowed_redaction_items` dropped the `is_pr_manager` paths.
- Regression test : a PR-RELATIONS user who selects a Media BW where they're owner now gets 403 on `/wip/newsroom` (Alfred Delarue's exact scenario).
- Invariant pinned : a `PM_JR_ME` micro-enterprise journalist who is the owner of their own BW Micro keeps full Newsroom access.
- Stale "Fonctionnalités Newsroom" block removed from `B06_assign_missions.html` (was advertising features no longer available to PR Managers).

The Comroom / Eventroom PR Manager paths and the `PermissionType`-per-content gate stay in place. New product matrix : **Newsroom = journalists only ; Comroom + Eventroom = PR Managers welcome, gated per-permission**.

## Manager Cleanup Sweep (May 29 AM)

Cohesive batch that retires the last vestiges of `RoleEnum.MANAGER` / `Organisation.manager` now that BWMi / BWMe carry the BW-management identity end-to-end.

- `User.is_manager` property deleted ; two call sites updated to the BW-manager check.
- `_is_manager` → `_is_bw_manager` in the Organisation profile view + template (iterates `RoleAssignment` BWMi / BWMe on the org's BW).
- Dead Org-level helpers removed : `add_managers_emails()`, `change_managers_emails()` + their tests.
- Deprecated `manager` column dropped from `/admin/show_org` ODS export.
- Faker fixtures + user-visible strings cleaned.

**End state** : the *managing* relationship of a User on an Organisation is only expressed through a BWMi / BWMe `RoleAssignment` on the BW of that Org. To answer "who manages org X" : `get_active_business_wall_for_organisation(org)` + walk `bw.role_assignments`.

## BW Owner Multi-Layer Safety Net (May 29 PM)

Logical follow-on : "an active BW always has an owner" becomes an invariant.

- New helper `_check_bw_owner_removal(user)` in `admin/utils.py`, wired into all three Org-mutation entry points : `set_user_organisation`, `remove_user_organisation`, `set_user_organisation_from_ids`. Returns an error string instead of silently stripping the membership.
- `/admin/show_user` `remove_org` action flashes the error on failure and skips the commit.
- Same protection extended to BW finalize (`bw_activation/routes/stage3.py`), Stripe webhook (`stripe/views/webhook.py`), and `/admin/show_org` (Organisation deletion blocked when a BW exists ; 598-line restructure of the admin actions panel for clearer dependency display).
- Tests pinned : (a) every BW creation propagates `bw_id` back onto its Org, (b) `delete_organisation` refuses while a BW exists, (c) BW owner can't be removed from their organisation.

The DB layer doesn't enforce these invariants (no FK, no trigger) — pure application-layer defence. The 4 entry points cover the public surface. A SQL CHECK / trigger is the next step ; not landed this week.

## Other Fixes (May 29)

- `wip/pages/opportunities.j2` crashed on `url_for(None)` when a contact's organisation had been cleared (user who quit their org). Wrap in `{% if organisation %}`.
- New `scripts/remove_all_bw.py` (dev utility to start from a clean BW state when iterating on the activation flow locally).
- WIP : `stage3.py` + `services/stripe/utils.py` extended to fetch the subscription product from Stripe alongside the one-shot payment. Not finalised.

## Trello Bug Fix Wave — 24 Tickets In Two Days (May 25-26)

Each ticket : root-cause analysis → TDD failing test → fix → 1 commit. Most fixes land with a regression test pinned to post-fix behaviour ; many also extend `e2e_playwright/regressions/test_bugs_*.py`.

- **#0050** PR Agency activation card — pricing default kept.
- **#0061** Avis "non-mais" suggested colleague flow stabilised.
- **#0068** Avis-enquête mail wording (AiPRESS24 wordmark, sender job, CTA) + F2F branch fix : code branched on `rdv_type.name == "IN_PERSON"` but the enum member is `F2F`, so face-à-face emails carried an empty type and no address.
- **#0070** Phase breadcrumbs across the WIP step-nav.
- **#0071** part 1 — dropped dead "contact us" fallback in the attaché selector ; part 2 — finalise a DRAFT BW on `/BW/confirmation` revisit so the user lands on an active BW.
- **#0075** part 2 — the attaché dropdown now surfaces BWPRi (internal) **and** BWPRe (external — owners of active PR-Agency partner BWs), via refactored `press_officer_emails`. Part 3 — the "Non, mais je suggère" radio stays clickable when no colleague is eligible.
- **#0088** Change-email confirmation redirect.
- **#0095** Taxonomies organisation-type partial display.
- **#0107** BW step 1 fonction prioritised per BW type.
- **#0118** Events filter leak between users at login.
- **#0122** BW invitation flow — confirm-partnership URL regression test added.
- **#0126** XSS systemic — autoescape on `.j2`, `Markup` wrap on macros, `SanitizedHTML` TypeDecorator at write + read.
- **#0128** Carrousel communiqué — Auteur header alignment.
- **#0129** Publisher BW name on /events/ list cards + detail aside.
- **#0130** Invitation email normalisation (lowercase + strip) at storage AND lookup.
- **#0131** Long-snowflake leak in HTML label.
- **#0132** parts 2-5 — Sujet workflow follow-ups (destinataire-side accept route, byline author, XSS sentinels, status flow).
- **#0133** Stages B1-B3 of the BW configurator alignment.
- **#0135** delegated events visible on the agency BW's Events tab. Root cause : `OrgEventsTab.label` + `OrgVM.get_events()` filtered on `publisher_id == org.id` only ; siblings (`OrgPressBookTab`, `OrgPressReleasesTab`) already used the dual-case `_press_releases_for_org_clause`. New helper `_events_for_org_clause` mirrors it. 5 regression tests.
- **#0142** step 4 « Gérer la liste des membres » modal harmonised with other BW configurator steps.
- **#0154** step-nav extended from Avis d'Enquête to Articles / Communiqués / Events.
- **#0166** `get_manageable_business_walls_for_user` now also lists client BWs reachable through active partnerships.
- **#0169** parts 1+2 — when a client revokes a PR partnership, the agency PDG gets a bell notification + mail. Part 3 — new "Partenariats RP terminés" section in `/preferences/invitations` with a "Confirmer" button that hard-deletes the revocation row.
- **#0170** "Créneaux proposés" block dropped from the RDV details page once a slot is accepted.
- **#0171** docstring + comment in `DualSelector` : candidate-pool gating ("only show categories with ≥ 1 indexed member") is intentional, not a bug. Erick had reported it as a missing entry — clarification pending.
- **#0172** `Event.publish()` refuses to flip to PUBLIC when `start_time` / `end_time` is None. Root cause : the `DateFilter` on `/events/` evaluated `NULL >= today` to NULL, silently hiding the event from the public listing even though WIP showed PUBLIC.

## "À Vérifier" Pile Review

Reviewed the 14 cards to confirm interpretation matches Erick's intent and each has a regression test :

- **12/14 fully verified**.
- **#0135** had only a 500-crash regression test ; visibility side (delegated event must appear on **both** Events tabs) wasn't pinned. Fixed + tested this session.
- **#0171** is not a bug — candidate-pool gating is by design. To re-clarify with Erick rather than re-close.

## Today's Bugs (May 27)

- **#0173** — RDV details page returned 403 for the expert of the contact. Root cause : `AvisEnqueteWipView.before_request` only authorised `rdv_accept` / `rdv_details` / `rdv_cancel` for users with the `EXPERT` community role. Nina is BWPRi (PRESS_RELATIONS) ; Isabelle is Enseignant.e-Chercheur.e (ACADEMIC). Neither holds EXPERT, so both got 403 on their own RDV. Fix : role gate → per-contact gate (`user.id ∈ {journaliste_id, expert_id}`). Same precision filter as `rdv_confirm`. 2 regression tests.
- **#0071 / #0174** — the picked press officer never received the avis email. Root cause : the `oui_relation_presse` branch of `media_opportunity_post` stored `contact.email_relation_presse` but never propagated. New `AvisEnqueteService.associate_press_officer(contact, press_officer_email, url_builder)` modelled on `suggest_colleague` : validates the email against the press officer pool, creates a new `ContactAvisEnquete`, posts bell notification, sends the avis email. 2 unit tests (happy path + tampered-email defence).

## Database Defence — UNIQUE on `aut_roles_users`

Companion DB-level fix to JD's Python defence (`2f7d18cf`, "do not crash if User roles are duplicate"). His list-comprehension rewrite of `User.remove_role` handles in-memory duplicates gracefully ; the UNIQUE constraint prevents new duplicates from being inserted in the first place.

Migration `78cb620e679d_unique_constraint_on_aut_roles_users.py` :

```sql
DELETE FROM aut_roles_users a USING aut_roles_users b
WHERE a.ctid < b.ctid
  AND a.user_id = b.user_id
  AND a.role_id = b.role_id;

ALTER TABLE aut_roles_users
  ADD CONSTRAINT uq_aut_roles_users_user_role
  UNIQUE (user_id, role_id);
```

Mirrored in the SQLAlchemy `Table` declaration so `create_all()` builds the constraint too (covers SQLite). Roundtrip upgrade ↔ downgrade verified.

2 regression tests : Python defence (`remove_role` purges both in-memory duplicates) + UNIQUE constraint (duplicate insert raises `IntegrityError`).

## Test Infra Debt

- **`test_resolved_bugs.py` split** : the monolithic 1805-line file became 4 per-ticket-range batches (`test_bugs_0050_0088.py`, `0095_0128`, `0129_0132`, `0133_0172`) + `_shared.py` for helpers. No behavioural change.
- **`test_avis_lifecycle.py` — dynamic discovery** : the two-user lifecycle test hardcoded an `AVIS_ID` / `CONTACT_ID` / `EXPERT_EMAIL` triple. The contact was hard-deleted by `prune_unselected_contacts` the last time the avis was re-targeted ; test crashed with 404. Replaced with a runtime walk : PRESS_MEDIA profiles → their avis → reponses-page rows → first quadruple `(journalist, avis, contact, expert)` where the expert can drive the OUI → propose → accept → confirm → cancel lifecycle. Aptitude probe visits `/wip/opportunities/{cid}` and checks for `<form id="avis-response-form">` (rendered only when the contact is unanswered AND the expert's org has an active BW). Companion template change : inert `data-contact-id` on each `<tr>` of `reponses.j2` so discovery can locate EN_ATTENTE rows.
- **`is_minio_available` catch widened** : when MinIO is down, botocore's redirect-from-error chain surfaces a `TypeError` (raised deep in bucket-name validation when fed a `None` bucket). The narrow `(ClientError, BotoCoreError, OSError)` catch missed it ; pytest collection crashed instead of skipping cleanly. Broadened to `Exception`.

## Stripe Dashboard Doc Finalised For EH

Two complementary updates in `local-notes/stripe/` :

- §0 « Mode d'intégration : Checkout » added at the top of `stripe-dashboard-EH.md` — answers Erick's Stripe wizard question "Comment souhaitez-vous accepter les paiements récurrents ?" : option 2 (Checkout) is the imposed choice because the existing code uses Pricing Tables + Checkout Sessions + `checkout.session.completed` webhook event.
- "Pourquoi Checkout (et pas Payment Links ni Elements)" section added to `stripe-principles-EH.md` : 3-row comparison, dev cost, PCI-DSS compliance (SAQ A vs SAQ A-EP vs SAQ D), 3 blocking technical reasons against Payment Links (no `client_reference_id`, no tiered pricing dynamic, no Customer Portal integration), trade-off mitigation for the domain switch. Decision dated 2026-05-26.

## Trello Pile Movement

Moved to `a-verifier/` : **#0173**, **#0174**, **#0071**. Plus Erick's informal May-28 bug ("Newsroom visible for PR Agency director") — fixed by JD's revert + 2 regression tests ; no Trello card.

`#0078` (Langues filter on `/swork/organisations`) stays in `qualifies/` pending product clarification — no `langues` column on `BusinessWall` ; only `KYCProfile.langues` at the user level. Semantics ("orgs whose ≥ 1 member speaks X") needs arbitration.
