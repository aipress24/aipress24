# Changes Week 6, 2026

## Geographic Filtering System

Country / department / city filters added across multiple modules.

- **SWORK** : members and organisations lists get the new filters via HTMX-based selectors ; zip-code search enabled in the top search bar ; active filter bar shows the actual country name.
- **News** : country / department / city filters on articles + communiqués.
- **Events** : country / department / city filters + zip-code search + search-field placeholder.
- **WIP** : `pays_zip_ville` + `pays_zip_ville_detail` location fields added to `Sujet`, `Commande`, `AvisEnquete` forms + models.

## Avis d'Enquête — Relation Presse Status

- New status `ACCEPTE_RELATION_PRESSE` (workflow updated).
- Dedicated email notification for relation-presse acceptance.
- `User.metier_fonction` property (journalism function + main métier) included in notification emails.

## Model Refactoring

Computed properties converted to SQLAlchemy hybrid properties (query-able) :

- `KYCProfile.ville` and `.departement` — enables filtering by city / department.
- `User.code_postal` and `Organisation.code_postal` — replace `zip_code`.
- `Addressable.departement` renamed to `departement_deprecated`.

## Bug Fixes

- RDV : "aucun message" displayed when message empty.
- Press release detail page : crash fix.
- Event detail page : crash + slide display fix.
- Admin : broken profile-validation links (initial + modifications) fixed ; left-menu link to `/admin/exports` fixed.
- Country name shown in active filter bar.

## HTMX Migration

SWORK members + organisations lists selectors migrated to HTMX (responsiveness, fewer reloads).

## Database Migrations

`_add_status_accepte_relation_presse`, `_rename_deprecated_addressable_`, `_add_geo_loc_to_avis_enquete`, `add_geo_loc_to_sujet_commande`.

## Testing

- Test for `StatutAvis.ACCEPTE_RELATION_PRESSE`.
- Updated tests for new SWORK selectors.
- Sender-job attribute in Avis emails tested.
- Friday-edge-case date tests fixed.

## Infrastructure

- Version bump : 2026.02.05.1 + dependency updates.
