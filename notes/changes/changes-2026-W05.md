# Changes Week 5, 2026

## Avis d'Enquête — Expert Targeting Selectors

9 new selectors added for fine-grained expert filtering : `TypeEntreprisePresseMedias`, `TypePresseMedias`, `Langues`, `FonctionJournalisme`, `FonctionPolitiquesAdministratives`, `FonctionOrganisationsPrivees`, `FonctionAssociationsSyndicats`, `CompetencesGenerales`, `CompetencesJournalisme`.

Selectors refactored into a dedicated `expert_selectors.py` (split from `expert_filter.py`) ; each selector follows the same pattern with full test coverage.

## Avis d'Enquête — UI/UX

- Lines now sorted by modification time (null values last) ; modification date displayed.
- `LifecycleMixin` sets `modified_at = created_at` on creation ; event listener enabled for automatic updates.
- UI terminology : 'expert' → 'profil' or 'contact' for clarity.
- RDV details : contextual return link (expert → opportunities ; journalist → RDV list).

## News Tab View

- Label "tab view" → "vue générale".
- Fixed filter-removal behaviour.

## Bug Fixes

- Organisation invitation acceptance fixed (was broken).
- BW page routing to `org-profile` fixed.
- Blank image fallback for organisations / sliders when bucket is broken.

## Testing

- Tests for all 9 new selectors.
- Fixed `test_expert_filter_service.py`.

## Infrastructure

- Alpine CI builds temporarily disabled.
- Version bump : 2026.01.23.1.
