# Changes Week 9, 2026

## Business Wall — Role Invitations

- New `BWRoleInvitationMail` mailer + `send_role_invitation_mail()`.
- BWMI (internal manager) and BWPRI (internal PR) invitation flows wired with email + role assignment.
- New confirmation page for BW role invitations (`confirm_role_invitation`) using a redirect pattern.
- `bw_managers_ids()` switched to a generic `bw_roles_ids()` helper.
- BWME (external manager) role management added.
- `ensure_roles_membership()` ensures all role assignments stay within current org members.
- User lists filtered by `user.active`.

## Business Wall — PR Agency Partnerships

Partnership model :

- Partnership now references `BusinessWall.id` (was `Organisation.id`). Migration added.
- New `BusinessWall.name` field and `BusinessWall.name_safe` property ; `name_safe` used in early activation stages.

PR Agency lookup helpers : `get_current_press_relation_bw_list`, `get_pending_press_relation_bw_list`, `get_press_relation_bw_list`, `bw_pr_managers_ids`, `get_current_pr_bw_info_list`, `get_pending_pr_bw_info_list`.

Invitation workflow :

- Rewritten using Partnership invitation status.
- Specific confirmation page for Partnership invitations ; pending / rejected / expired invitations surfaced.
- BW with status "invited" hidden from available-PR lists.
- `invite_pr_provider()` built on top of `invite_user_role()`.
- Pending PR BW list shown in `B04_manage_external_partners.html`.

UI : specific empty-state message + inactive button for BWPRe when no PR agency in list ; current external partners listed ; dashboard block numbering adapted for PR BW (block 4 skipped, block 5 renumbered to 4).

## Business Wall — Paid Activation

- New `create_new_paid_bw_record()` for paid BW creation.
- Links to CGV and "Accord de diffusion" on the pricing page + confirmation page.
- "Retour choix d'activation" link removed from paid confirmation pages.

## Bug Fixes

- `non_authorized` → `not_authorized` endpoint name typo (3 files).
- `B05_assign_missions.html` fixed for BW without newsroom feature.
- `get_pending_press_relation_bw_list` actually returns the BW of the assigned user.
- `get_pending_pr_bw_info` actually returns a value.
- BW PR retrieval fixed on the confirmation page.
- Wire filter typing : `callable()` check added.

## Tests

Integration tests in `tests/b_integration/modules/bw/` (`test_bw_activation`, `test_bw_routes`, `test_stages_b1_b3`, `test_stages_b4_b6`, `test_bw_dashboard`, plus shared `conftest.py`). `send_role_invitation_mail` mocked to avoid real sends. Active users created and `g.user` set where needed.

Unit tests : `BWRoleInvitationMail`, `ensure_roles_membership`, `change_bwmi_emails` / `change_bwpri_emails`, `bw_pr_managers_ids`, `get_current_press_relation_bw_list`, `get_pending_press_relation_bw_list`, `create_new_paid_bw_record`.

## Code Quality

- Debug symbols + unused code removed.
- Linter fixes ; dependencies updated.
