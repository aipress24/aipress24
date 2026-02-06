# Changes Week 6, 2026

## Geographic Filtering System

Major addition of geographic filters (country, department, city) across multiple modules.

### SWORK Module

- **Member List**: Country, department, and city filters with HTMX-based selectors
- **Organisation List**: Same geographic filters applied
- Search by zip code enabled in top search bar for both members and organisations
- Display actual country name in filter bar

### News Module

- Added country/department/city filters to articles
- Added country/department/city filters to communiqués (press releases)

### Events Module

- Added country/department/city filters
- Added search by zip code
- Added placeholder to search field

### WIP Module (Publication Workflow)

Geographic location fields (`pays_zip_ville`, `pays_zip_ville_detail`) added to:

- **Sujet** forms and model
- **Commande** forms and model
- **AvisEnquete** forms and model

## Avis d'Enquête - Relation Presse Status

New workflow status for press relations acceptance.

### Key Changes

- New status: `ACCEPTE_RELATION_PRESSE`
- Dedicated email notification for relation presse acceptance
- Workflow updated to handle new status

### Email Improvements

- Sender job (`metier_fonction`) now included in notification emails
- New `User.metier_fonction` property combining journalist function and main métier

## Model Refactoring

### Hybrid Properties

Converted computed properties to SQLAlchemy hybrid properties for query support:

- `KYCProfile.ville` - enables filtering by city
- `KYCProfile.departement` - enables filtering by department
- `User.code_postal` - replaces `zip_code`
- `Organisation.code_postal` - replaces `zip_code`

### Deprecations

- `Addressable.departement` renamed to `departement_deprecated`

## Bug Fixes

- **RDV Display**: Show "aucun message" when RDV message is empty
- **Press Release Detail**: Fixed crash when displaying press release details
- **Event Detail**: Fixed crash and slide display issues
- **Admin Links**: Fixed broken links for profile validation pages (initial and modifications)
- **Admin Menu**: Fixed left menu link to `/admin/exports`
- **Country Display**: Show actual country name in active filter bar

## HTMX Migration

- SWORK member list selectors migrated to HTMX
- SWORK organisation list selectors migrated to HTMX
- Improved responsiveness and reduced page reloads

## Database Migrations

| Migration | Description |
|-----------|-------------|
| `_add_status_accepte_relation_presse.py` | Add new ACCEPTE_RELATION_PRESSE status |
| `_rename_deprecated_addressable_.py` | Rename Addressable.departement |
| `_add_geo_loc_to_avis_enquete.py` | Add geographic columns to AvisEnquete |
| `add_geo_loc_to_sujet_commande.py` | Add geographic columns to Sujet and Commande |

## Testing

- Fixed test for `StatutAvis.ACCEPTE_RELATION_PRESSE`
- Updated tests for new SWORK member list selectors
- Updated tests for new SWORK organisation list selectors
- Fixed tests for sender job attribute in Avis d'Enquête emails
- Fixed tests failing on Fridays (date-related edge cases)

## Infrastructure

- Version bump: 2026.02.05.1
- Dependencies update
