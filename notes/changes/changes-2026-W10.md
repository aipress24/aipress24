# Changes Week 10, 2026

## Business Wall — Data Entry Form

Many new BW fields added across identity, contact, location, organisation, editorial, interest, and activity dimensions :

- **Identity** : `name`, `name_official`, `name_group`, `name_institution`.
- **Contact** : `tel_standard`, `postal_address`, `site_url`.
- **Location** : `geolocalisation` + country / code / city.
- **Organisation** : `type_organisation` (dual-field with migration), `taille_organisation`, `type_entreprise_media`, `type_pr_agency`.
- **Editorial** : `positionnement_editorial`, `audience_cible`, `type_presse_media`, `periodicite` (needs ontology entry).
- **Interest** : `interest_political_detail`, `interest_economics_detail`, `interest_association_detail` + multi-select fields for "centre d'intérêt".
- **Activity** : `secteur_activite_couvert`, `clients`.

Image management :

- New `cover_image` (bandeau) as a second image item.
- `gallery_images` field on `BusinessWall` ; add / remove multiple images ; helper utilities.

Form improvements :

- Generic `updateDualMultiSelect()` JS helper for dual-selection fields.
- `permit_selection_of_dual_field_type_organisation()` ; BW form field for "liste des membres" removed.

## Business Wall — PR Missions

- New `BusinessWall.missions` field (dict, stage-6 missions) + migration.
- `apply_bw_missions_to_pr_user()` applies BW missions to a PR user.
- `sync_all_pr_missions()` synchronises all PR permissions on mission change.
- Missions applied to BWPRe when accepting role (using PR owner.id) ; applied to new BW PR on role acceptance.
- `PermissionType` enum used consistently for stage-6 permission names.

## Bug Fixes

- "Enregistrer et continuer" actually navigates to next page.
- BW form footer mention removed.
- Single-session-commit fix in BW data management.
- Bad import removed ; wrong attribute on `BusinessWall` removed.
- `PermissionType` values + BW stage-6 missions code fixed.

## Module Swork — Cleanup

- `SWORK_LIST_LIMIT = 100` constant in `settings.py` ; hardcoded `.limit(100)` replaced in members / organisations / groups lists.
- Hardcoded placeholder URLs in `views/group.py` replaced with `group.logo_url` + `group.cover_image_url`, falling back to `/static/img/blank-square.png` / `gray-texture.png`.
- Docstrings added to `BaseList`, `Filter`, `FilterByCity`, `FilterByDept`, `MembersList`, `OrganisationsList`, `GroupsList`.

## Tests

New test files :

- `pywire/test_routes.py` (6 tests : Livewire sync inputs, fire events).
- `cli/test_nav.py` (9 tests : mock-user-with-roles, role checking, filter resolution).
- `stripe/test_stripe_utils.py` (17 tests : key validation, config, pricing-table loading).
- `pdf/test_pdf_base.py` (4 tests).
- `lib/test_htmx.py` (4 tests : fragment extraction).
- `lib/test_controllers.py` (9 tests : decorators + dispatcher).

Documentation :

- New `notes/dev/testing.md` : stubs vs mocks, pure functions, ViewModels, transaction isolation, functional-core / imperative-shell pattern.

Refactoring :

- `test_utils.py` → `test_stripe_utils.py` and `test_base.py` → `test_pdf_base.py` to avoid pytest import collisions.
- `ClassVar` type error in `swork/components/base.py` fixed.

## DevOps

- Docker config (`Dockerfile`, `docker-compose.yml`) + Hop3 config.
- Misc cleanup, linter fixes.
