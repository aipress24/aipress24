# Changes Weeks 1-2, 2026

## Avis d'Enquête — RDV (Appointment) System

Full implementation of the journalist ↔ expert rendez-vous workflow.

- State machine : `NO_RDV → PROPOSED → ACCEPTED → CONFIRMED`. Three RDV types : phone, video, face-to-face.
- Journalists propose 1-5 time slots ; experts pick one and may add notes.
- New RDV table view (all contacts with their status), RDV details view, management interface, link from opportunities.
- Validation rules : slots must be future, weekdays, business hours (9 h-18 h) ; contact details required per RDV type.

## Service Layer Architecture

Major refactor extracting business logic from CRUD views into services.

- `AvisEnqueteService` orchestrates the RDV workflow (propose / accept / confirm / cancel), expert notifications, contact storage and filtering. (JD note : email notifications not yet implemented at this stage.)
- `ExpertFilterService` : 8-selector multi-criteria expert filter, session-scoped state, HTMX request parsing.
- WIP CRUD view shrinks **877 → 390 lines (-55 %)** ; domain validation moves into models ; components become testable via DI.

## Type Checking & Code Quality

- Runtime type checking via `typeguard` (replaces `beartype`). 68+ type errors fixed.
- Navigation registry pattern : `blueprint.nav = {...}` monkey-patch replaced with a clean `configure_nav()` + TypedDict. 8 modules migrated (admin, biz, events, preferences, search, swork, wip, wire).

## Navigation ACL System (ADR 003)

Role-based access control completed.

- Section-level ACL inherited by child routes (admin, preferences/SELF).
- `GUEST` role removed ; new `SELF` magic role (visible to all authenticated users).
- Personal routes protected (billing, performance, mail, delegate) ; org routes protected with MANAGER / LEADER.
- Four-layer security : doorman (path) → blueprint hooks → nav ACL → view checks. Defence in depth.

## Legacy Cleanup

- `preferences/pages/` directory deleted (10 legacy files), 28 legacy Page-class tests dropped (9 useful ones kept). Replaced with Flask-Classful views.
- Admin module cleaned up ; e2e fixtures refactored ; circular imports fixed.

## Publication Workflow Spec + Notification Refactor

- New spec `notes/specs/cycle-de-publication.md` documents Sujet → Commande → Avis → Article → Justificatif (v1.1, with client feedback).
- `JustifPublication` (complex lifecycle) removed, replaced by `NotificationPublication` — fire-and-forget : `created = sent`, `notified_at` stamped on creation, no email/in-app tracking. `NotificationPublicationContact` links notification to expert contacts. (Notification = WIP alert ; Justificatif = BIZ product.)
- Migrations `8c27eefc5851` (drop `nrm_justif_publication`) + `9763afdb9033` (create new tables).

## Status Field Enum Migration

- `Sujet.status`, `Commande.status`, `AvisEnquete.status` switched from `Mapped[str]` to `Mapped[PublicationStatus]` (consistent with Article/Communique/Event). Type safety + IDE autocomplete.
- Migration `a1b2c3d4e5f6` converts VARCHAR → enum ; empty strings → `DRAFT`.

## Testing

Comprehensive test plan (`notes/specs/test-plan-cycle-publication.md`) implemented :

- 29 ExpertFilterService, 17 ContactAvisEnquete response, 10 NotificationPublication, 10 publication-cycle integration, 3 HTMX state, 5 expert flow integration, 4 notification sending readiness, 15 Avis views e2e, 13 RDV workflow e2e, 3 full-cycle integration. **109 new tests** ; 237 WIP-module tests passing ; 1960+ total passing.
