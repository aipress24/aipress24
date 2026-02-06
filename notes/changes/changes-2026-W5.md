# Changes Week 5, 2026

## Avis d'Enquête - Expert Targeting Selectors

Major expansion of the expert targeting system with 9 new selectors for fine-grained expert filtering.

### New Selectors

| Selector | Purpose |
|----------|---------|
| `TypeEntreprisePresseMediasSelector` | Filter by press/media company type |
| `TypePresseMediasSelector` | Filter by press/media type |
| `LanguesSelector` | Filter by languages |
| `FonctionJournalismeSelector` | Filter by journalism function |
| `FonctionPolitiquesAdministrativesSelector` | Filter by political/administrative function |
| `FonctionOrganisationsPriveesSelector` | Filter by private organization function |
| `FonctionAssociationsSyndicatsSelector` | Filter by association/union function |
| `CompetencesGeneralesSelector` | Filter by general competencies |
| `CompetencesJournalismeSelector` | Filter by journalism competencies |

### Architecture

- Refactored selectors into dedicated `expert_selectors.py` module (split from `expert_filter.py`)
- Each selector follows consistent pattern with full test coverage

## Avis d'Enquête - UI/UX Improvements

### Modification Tracking

- AvisEnquete lines now sorted by modification time (null values at end)
- Modification date displayed in the interface
- `LifecycleMixin` now sets `modified_at` to `created_at` on creation
- Enabled event listener in `LifecycleMixin` for automatic timestamp updates

### Terminology Update

- Replaced 'expert' with 'profil' or 'contact' in UI for clarity

### RDV Details Page

- Now displays contextual return link:
  - Expert: link to opportunities list
  - Journalist: link to RDV list

## News Tab View

### Improvements

- Renamed label: "tab view" → "vue générale"
- Fixed filter removal behavior (now works as expected)

## Bug Fixes

- **Organization Invitation**: Fixed accepting invitation to join an organization (was broken)
- **BW Routing**: Fixed routing on Business Wire page to org-profile
- **Missing Images**: Show blank image for organisations when image bucket is broken
- **Slider Images**: Display blank image for missing slider images instead of error

## Testing

### New Selector Tests

Comprehensive test coverage for all new expert targeting selectors:

- `test_TypeEntreprisePresseMediasSelector`
- `test_TypePresseMediasSelector`
- `test_LanguesSelector`
- `test_FonctionJournalismeSelector`
- `test_FonctionPolitiquesAdministrativesSelector`
- `test_FonctionOrganisationsPriveesSelector`
- `test_FonctionAssociationsSyndicatsSelector`
- `test_CompetencesGeneralesSelector`
- `test_CompetencesJournalismeSelector`

### Test Fixes

- Fixed `test_expert_filter_service.py`

## Infrastructure

- Disabled Alpine CI builds (temporarily ignored)
- Version bump: 2026.01.23.1
