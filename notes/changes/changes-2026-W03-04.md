# Changes Weeks 3-4, 2026

## Avis d'Enquête — RDV Workflow Completion

Confirmation popups on all critical RDV actions (acceptance, slot proposal, accept / decline, decline-all, cancellation by either party).

Full email notification chain :

- `ContactAvisEnqueteAcceptedMail` — expert → journalist on acceptance.
- `ContactAvisEnqueteRDVProposalMail` — journalist → expert on slot proposal.
- `ContactAvisEnqueteRDVAcceptedMail` — expert → journalist on RDV acceptance.
- `ContactAvisEnqueteRDVConfirmedMail` — journalist → expert on confirmation.
- `ContactAvisEnqueteRDVCancelledMail` — cancellation notification.

Opportunities view : new status messages ("Attente de dates", "Opportunité déclinée", "Nouvelle opportunité"), confirmed RDV displayed in list, reverse-date sort, auto-redirect after response, auto-flip `AvisEnquete` DRAFT → PUBLIC when sent to experts.

RDV cancellation : both parties can cancel (with popup) ; emails sent ; new `ContactAvisEnquete.can_cancel_rdv()` permission check.

## Email System Improvements

- Explicit logging of sender, recipient, subject, status for every email. Sender name (not just `contact@aipress`) included.
- Rate limiter switched from monthly to **20 mails / 7 days** ; `bypass_quota` flag for system-critical mails ; monthly cap 200.
- Mailer refactor : dataclass-based templates ; recipient + sender in context ; `sender_name` → `sender_mail` (clarity) ; `sender_full_name` field added everywhere ; opportunity URL embedded in proposal emails.

## Expert Filter Service

- `ExpertFilterService.initialize()` now requires `avis_enquete_id`. Each Avis maintains independent filter state via scoped session keys — no more bleed between enquêtes.
- UI : "Aucun expert" → "Aucun nouvel expert" ; selectors synced with backend ; ciblage list empty for new Avis instances.

## CLI Reorganisation

Flask CLI commands reduced from 29 to 21 top-level entries by grouping :

| Group | Commands |
|---|---|
| `data` | bootstrap-users, fetch-bootstrap-data, load-db, upgrade-ontologies |
| `media` | dump-photos, upload-photos |
| `dev` | debug, check, components, packages |
| `fix` | roles, test-user |

New list commands : `flask roles list`, `flask users list` (with `--active` / `--all` / `--limit`). Console cleanup : `pkg_resources` deprecation warning from passlib silenced, "Configuring logging" startup message removed.

## Bug Fixes

- WIP Table pagination aligned with admin/table.py.
- HTMX self-redirect now triggers page refresh.
- Naive RDV dates default to UTC.
- Cancellation mail sent before state update (was inverted, mail was empty).
- Null-check `contact.date_rdv` before mail notification.
- Opportunity page access restricted to the expert only.

## Testing

- Unit tests for all mailers ; e2e tests for RDV refuse (decline slot, refuse button) + cancellation workflow ; unit tests for ExpertFilterService session-key isolation + state independence.
- `EMAILS_MAX_SENT_LAST_PERIOD` bumped 20 → 200 for dev tests.
- Test fixes : `test_expert_accept_rdv_submission`, RDV workflow e2e, avis-enquête notification mail.

## Infrastructure

- CI updates (Alpine profile aligned with Ubuntu / Rocky).
- Type checker (`ty`) configuration tweaks.
- Dependency updates.
