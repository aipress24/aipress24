# Changes Weeks 3-4, 2026

## Avis d'Enquête - RDV Workflow Completion

Full completion of the RDV (rendez-vous) notification and interaction workflow.

### Confirmation Popups

All critical RDV actions now require user confirmation via popup dialogs:

- **Acceptance**: Expert confirms acceptance of Avis d'Enquête
- **Proposal**: Journalist confirms RDV time slot proposal
- **Accept/Decline RDV**: Expert confirms response to proposed slots
- **Decline All**: Expert can decline all proposed RDV dates at once
- **Cancellation**: Both journalist and expert can cancel confirmed RDV

### Notification Emails

Complete email notification chain for RDV workflow:

- `ContactAvisEnqueteAcceptedMail`: Expert → Journalist on acceptance
- `ContactAvisEnqueteRDVProposalMail`: Journalist → Expert for RDV proposal
- `ContactAvisEnqueteRDVAcceptedMail`: Expert → Journalist on RDV acceptance
- `ContactAvisEnqueteRDVConfirmedMail`: Journalist → Expert on RDV confirmation
- `ContactAvisEnqueteRDVCancelledMail`: Notification when RDV is cancelled

### Opportunities View Improvements

- New status messages: "Attente de dates", "Opportunité déclinée", "Nouvelle opportunité"
- Display confirmed RDV in opportunities list
- Sort opportunities by reverse date
- Auto-redirect to opportunities after RDV response
- Auto-update AvisEnquete status from DRAFT to PUBLIC when sent to experts

### RDV Cancellation

- Journalist can cancel RDV with confirmation popup
- Expert can cancel RDV with confirmation popup
- Cancellation emails sent to notify the other party
- `ContactAvisEnquete.can_cancel_rdv()` method for permission check

## Email System Improvements

### Logging & Monitoring

- Explicit logging of sender, recipient, subject, and status for all emails
- Actual sender name now included in logged mail information (not just contact@aipress)
- Better traceability for debugging email issues

### Rate Limiting

- Mail limiter changed from monthly to weekly: **20 mails / 7 days**
- Added `bypass_quota` option for system-critical emails
- Max monthly limit set to 200 mails

### Mailer Architecture

- Refactored to use dataclasses for mailer templates
- Added recipient and sender to mailer context
- Cleaner template rendering with structured data

## Expert Filter Service

### State Isolation

- `ExpertFilterService.initialize()` now requires `avis_enquete_id`
- Each Avis d'Enquête maintains independent filter state
- Session keys scoped to specific Avis d'Enquête instance
- Prevents filter state bleeding between different enquêtes

### UI Improvements

- Ciblage experts message: "Aucun expert" → "Aucun nouvel expert"
- Selectors now properly synchronized with backend state
- Ciblage list properly empty for new AvisEnquete instances

## CLI Reorganization

Reduced Flask CLI commands from 29 to 21 top-level entries by grouping related commands.

### New Command Groups

| Group | Commands |
|-------|----------|
| `data` | bootstrap-users, fetch-bootstrap-data, load-db, upgrade-ontologies |
| `media` | dump-photos, upload-photos |
| `dev` | debug, check, components, packages |
| `fix` | roles, test-user |

### Migration Examples

```bash
flask data bootstrap-users     # was: flask bootstrap-users
flask data load-db             # was: flask load-db
flask media dump-photos        # was: flask dump-photos
flask dev check --full         # was: flask check --full
flask fix roles                # was: flask fix-roles
```

## Bug Fixes

- **Table Pagination**: Fixed WIP module Table pagination to match admin/table.py behavior
- **HTMX Refresh**: Fixed page refresh when redirecting to self with HTMX
- **RDV Dates**: Fixed handling of naive dates (now default to UTC)
- **Mail Order**: Cancellation mail now sent before state update
- **Null Check**: Verify `contact.date_rdv` is not None before mail notification

## Testing

### New Tests

- Unit tests for all mailers
- E2E test: `test_expert_refuse_rdv_submission_using_decline_slot()`
- E2E test: `test_expert_refuse_rdv_submission_using_refuse_button()`
- E2E test: RDV cancellation workflow
- Unit tests for ExpertFilterService session key isolation
- Unit tests for ExpertFilterService state independence across enquêtes

### Test Fixes

- Fixed `test_expert_accept_rdv_submission()`
- Fixed `tests/c_e2e/modules/wip/newsroom/test_rdv_workflow_e2e.py`

## Infrastructure

- CI configuration updates
- Type checker (ty) configuration tweaks
- Dependency updates
