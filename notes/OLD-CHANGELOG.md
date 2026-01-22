# Changelog

All notable changes to this project will be documented in this file.


## [2024.12.06.1] - 2024-12-06

### 🔧 Maintenance
- Updated dependencies to the latest versions.
- General cleanup and updates to the repository.

### 🚜 Refactor
- Adjusted ruff configuration.
- Renamed variables for clarity and maintainability.
- Set BICUBIC as the default interpolation method for image resizing.


## [2024.12.02.1] - 2024-12-02

### 🚀 Features
- Enhanced Stripe integration to retrieve product details and subscriptions.
- Introduced new fields in the `Organisation` class:
  - `validity_date` for subscription checks.
  - `is_bw_valid_date` to validate subscriptions.
- Implemented a free registration workflow for media-related cases.
- Added functionality to store subscribed product IDs in the `Organisation` class.

### 🐛 Bug Fixes
- Removed unused URL attributes (e.g., `github_url`, `linkedin_url`) from `Organisation`.
- Resolved product storage issue in the application.

### 🚜 Refactor
- Simplified Stripe subscription handling by removing custom templates for success and cancel pages, using the main template instead.


## [2024.11.29.1] - 2024-11-29

### 🚀 Features
- Integrated Stripe keys for enhanced payment processing.
- Implemented UI updates to display available product descriptions from Stripe.
- Added a new field `Organisation.number_customers` to track customer data.

### 🚜 Refactor
- Enhanced BW form rendering:
  - Improved UI consistency.
  - Streamlined generation and management for admin pages.
- Improved JavaScript code organization and readability.

### 🐛 Bug Fixes
- Adjusted placeholder text in KYC forms for better usability.
- Resolved issues related to CSS rendering for `htmx` and Alpine.js interactions.

### 📚 Documentation
- Updated README with a tentative roadmap for the project's future development.


## [2024.11.22.3] - 2024-11-22

### 🚀 Features
- Added buttons on the BW (Business Wall) registration page to allow users to register their organisations and automatically become managers of the newly created organisations.
- Implemented toggles on the admin page to manage the `Organisation.active` status.
- Introduced the `Organisation.is_auto_or_inactive` property for state-based validations.
- Added the `Organisation.active` attribute for enhanced organisation state tracking.

### 🐛 Bug Fixes
- Ensured BW registration pages do not display logos if unavailable.
- Improved regex validation rules.
- Ensured organisation-specific forms do not crash when fields are empty or optional.
- Corrected and unified label conventions:
  - "Business Wall for Agencies" → "Business Wall for Press Agencies."
  - "AiPRESS24 PRO" → "AiPRESS24 PRO."

### 🚜 Refactor
- Enhanced BW page UI for detecting and managing `org.bw_type` and `org.active` states.
- Improved labels and admin page controls.
- Renamed and reorganized imports across multiple modules to improve code readability and maintainability.
- Moved admin utility functions from `admin/pages/show_org.py` to `admin/utils.py`.
- Simplified SQLAlchemy models, including making certain fields like SIREN and TVA non-unique.


## [2024.11.18.1] - 2024-11-18

### 🚀 Features
- Added dynamic fields and validation popups to BW forms for better user experience and control.
- Enhanced the BW form to dynamically show or hide fields based on user roles (managers vs. others).

### 🐛 Bug Fixes
- Improved validation of fields and ensured placeholders are consistent across forms.
- Fixed issues where non-manager users were restricted from viewing some BW details.


## [2024.11.04.1] - 2024-11-04

### 🚀 Features
- Introduced `BWTypeEnum` to manage different subscription types for Business Wall (BW) organisations.
- Enhanced organisation forms to dynamically display all BW fields.
- Added export functionality to include emails of members, leaders, and managers in `.ods` format.
- Introduced invitation management:
  - Added an invitation button "Rejoindre."
  - Enabled multiple invitations per user.
  - Automatic garbage collection of orphaned `AUTO` organisations.

### 🐛 Bug Fixes
- Made `SIREN` and `TVA` fields in the `Organisation` class nullable and unique.
- Improved descriptions in the admin organisation modal windows.

### 🚜 Refactor
- Updated `Organisation` models to include new fields like `bw_type` for better categorisation and tracking.
- Improved the management of Business Wall subscriptions through simplified forms and validation logic.
- Simplified member counting logic for organisations.
- Enhanced invitation handling and organisation cleanup when users or their roles change.


## [2024.10.29.6] - 2024-10-29

### 🚀 Features
- Added modal confirmations for:
  - User removal from organisations.
  - User deactivation in the admin interface.

### 🐛 Bug Fixes
- Corrected button labels and improved the selector logic on admin pages.


## [2024.10.25.1] - 2024-10-25

### 🚀 Features
- Added an admin button to list invitations for organisations.
- Enhanced user invitations by allowing automatic organisation assignment based on invitation email.

### 🐛 Bug Fixes
- Improved uniqueness checks for email-based invitations.


## [2024.10.18.1] - 2024-10-18

### 🚀 Features
- Introduced the ability to manage lists of organisation managers and leaders via the admin interface.
- Enabled detailed views for organisations on the admin page.

### 🐛 Bug Fixes
- Fixed placeholder display issues in organisation forms.

### 🚜 Refactor
- Renamed `PreInscription` to `Invitation` for clarity.
- Streamlined exports and data presentation in `.ods` reports.


## [2024.10.10.1] - 2024-10-10

### 🚀 Features
- Added functionality to detect media direction during validation stages.

### 💅 UI/UX
- Improved design for newsroom cards.


## [2024.10.04.4] - 2024-10-04

### 🚀 Features
- Added light organisation pages with filtering capabilities by organisation family.

### 🚜 Refactor
- Replaced `OrganisationTypeEnum` with `OrganisationFamilyEnum` for clearer classification.
- Reorganised organisation-related models and constants.


## [2024.09.27.1] - 2024-09-27

### 🚀 Features
- Enhanced newsroom functionalities:
  - Integrated taxonomy for `orga_newsrooms`.
  - Added matchmaking features for newsroom queries.

### 🐛 Bug Fixes
- Resolved UI issues in newsroom pagination.


## [2024.09.12.1] - 2024-09-12

### 🚀 Features
- Added dynamic forms for BW (Business Wall) registration, supporting custom attributes and roles.
- Introduced validation triggers for specific modifications.

### 🐛 Bug Fixes
- Corrected issues with user role assignments and BW modifications.


## [2024.08.29.1] - 2024-08-29

### 🚀 Features
- Added user preferences for email and phone visibility.
- Updated ontologies for improved integration with KYC forms.

### 🐛 Bug Fixes
- Improved visibility and help messages in user profiles.


## [2024.08.07.1] - 2024-08-07

### 🚀 Features
- Enhanced organisation handling:
  - Automatic completion of organisation names.
  - Improved support for non-standard organisation types.

### 💅 UI/UX
- Tweaked profile and organisation-related form designs.


## [2024.07.19.1] - 2024-07-19

### 🚜 Refactor
- Optimised the loading and updating of zip code and country data for KYC forms.
- Streamlined ontology management processes.


## [2024.07.11.1] - 2024-07-11

### <!-- 0 -->🚀 Features

- Add /kyc/edit route (wip)

### <!-- 1 -->🐛 Bug Fixes

- Remove "nom_media" field for profiles using nom_media_insti
- Let use first element of list "nom_media" for "organisation_name"
- /kyc/edit route (without photo)
- Load photos from logged User

### <!-- 2 -->🚜 Refactor

- Match USER's 'hobbies' from KYC, guess User's 'organisation_name'
- Rename "hobbies" -> "Intérêts / hobbies" in kyc
- Remove /kyc/edit, use directly /kyc/profile to edit current logged user
- Faker load profil image (and apply ruff, isort)
- Faker updated for attribute tel_mobile and JS regex to check phone number updated

### <!-- 6 -->🧪 Testing

- Move playwright tests outside the source tree.
- Fix unit tests app/modules/kyc/tests/test_ontology_json.py
- Fix unit tests app/modules/kyc/tests/test_parser.py
- Fix unit tests app/modules/kyc/tests/test_model_tmp_blob.py
- Add missing file modules/kyc/tests/conftest.py

## [2024.07.03.1] - 2024-07-03

### <!-- 0 -->🚀 Features

- Merge new kyc (kyc2), (wip: conficting tables)
- Put "Français" as first choice in select list of KYC

### <!-- 1 -->🐛 Bug Fixes

- Merging kyc2, still pb with DB
- Fix kyc2 access to DB
- Apply isort & ruff to modules/kyc2
- Correction of blueprint kyc2 url_for()
- Use class User in admin/pages/kyc.py to replace MembershipApplication

### <!-- 2 -->🚜 Refactor

- Remove previous modules/kyc
- Rename modules/kyc2 -> modules/kyc
- Remove modules/kyc/vite directory
- Move CGU page from kyc to standard /static-pages/cgu.md

### <!-- 3 -->📚 Documentation

- Fix admonition
- Add TROUBLESHOOTING file to document common problems

## [2024.06.20.1] - 2024-06-20

### <!-- 3 -->📚 Documentation

- Tweak readme

## [2024.06.17.5] - 2024-06-17

### <!-- 0 -->🚀 Features

- Replace splash picture

## [2024.06.17.4] - 2024-06-17

### <!-- 3 -->📚 Documentation

- Readme update

## [2024.06.17.2] - 2024-06-17

### <!-- 1 -->🐛 Bug Fixes

- Botched search&replace

## [2024.06.17.1] - 2024-06-17

### <!-- 3 -->📚 Documentation

- Add extra information

## [2024.06.07.1] - 2024-06-07

### <!-- 3 -->📚 Documentation

- Cleanup

## [2024.05.24.1] - 2024-05-24

### <!-- 2 -->🚜 Refactor

- Remove unused module.

## [2024.05.22.3] - 2024-05-22

### <!-- 2 -->🚜 Refactor

- Don't use CDN for Flowbite

## [2024.05.17.1] - 2024-05-17

### <!-- 0 -->🚀 Features

- Images on articles.

## [2024.05.06.1] - 2024-05-06

### <!-- 1 -->🐛 Bug Fixes

- Use SQLA config from env var if present.

## [2024.04.26.3] - 2024-04-26

### <!-- 0 -->🚀 Features

- Remove "vignette"

## [2024.04.26.2] - 2024-04-26

### <!-- 0 -->🚀 Features

- Images on articles.

## [2024.04.26.1] - 2024-04-26

### <!-- 0 -->🚀 Features

- Wip

## [2024.04.19.1] - 2024-04-19

### <!-- 0 -->🚀 Features

- Image editor.

## [2024.04.18.1] - 2024-04-18

### <!-- 0 -->🚀 Features

- Add copyright.

## [2024.04.17.1] - 2024-04-17

### <!-- 2 -->🚜 Refactor

- Local imports.
- Publication

## [2024.04.12.1] - 2024-04-12

### <!-- 0 -->🚀 Features

- Add "view" mode to CRUD views.

### <!-- 2 -->🚜 Refactor

- Use specific models for Wire.

## [2024.04.11.3] - 2024-04-11

### <!-- 2 -->🚜 Refactor

- Dashboard

## [2024.03.22.1] - 2024-03-22

### <!-- 1 -->🐛 Bug Fixes

- Suppression d'objets dans WIP
- Filtrage sur les tables + refact class hierarchy in WIP.

## [2024.03.07.1] - 2024-03-07

### <!-- 0 -->🚀 Features

- KYC model.
- KYC model generator

## [2024.02.29.1] - 2024-02-29

### <!-- 1 -->🐛 Bug Fixes

- Upgrade flask-security broke an import.

### <!-- 2 -->🚜 Refactor

- Used enum for communities.

### Chore

- Deps

## [2024.02.16.1] - 2024-02-16

### <!-- 0 -->🚀 Features

- Newsroom

### <!-- 1 -->🐛 Bug Fixes

- Articles status in newsroom
- Add aenum for pyhon 3.10 compat.
- Article statuses.

### <!-- 2 -->🚜 Refactor

- Restore Python 3.10 compatibility.

## [2024.02.15.1] - 2024-02-15

### <!-- 0 -->🚀 Features

- Notifications
- Notifications.

### <!-- 1 -->🐛 Bug Fixes

- Boutons "annuler"
- Remove useless import
- Image form

## [2024.02.09.2] - 2024-02-09

### <!-- 0 -->🚀 Features

- Newsroom

## [2024.02.09.1] - 2024-02-09

### <!-- 0 -->🚀 Features

- Newsroom forms (wip)
- Newroom forms (rich text)
- Work on forms.
- Newsroom ui tweak.
- Newsroom

### <!-- 2 -->🚜 Refactor

- Simplify forms
- Move newsroom models to the newsroom module

## [2024.02.02.2] - 2024-02-02

### <!-- 0 -->🚀 Features

- Avis d'enquetes

### <!-- 1 -->🐛 Bug Fixes

- Avis d'enquete

## [2024.02.02.1] - 2024-02-02

### <!-- 0 -->🚀 Features

- Ciblage avis d'enquete

## [2024.02.01.2] - 2024-02-01

### <!-- 1 -->🐛 Bug Fixes

- Sélection des experts

## [2024.02.01.1] - 2024-02-01

### <!-- 0 -->🚀 Features

- Improve ciblage.

### <!-- 1 -->🐛 Bug Fixes

- Confusion between 2 classes called "article".
- Session service

### <!-- 2 -->🚜 Refactor

- Rename module

### Ci

- Use ubicloud
- Only support Python 3.12
- Fix config

### Devops

- Use Python 3.12.1

## [2024.01.31.1] - 2024-01-31

### <!-- 0 -->🚀 Features

- Renaming (WIP)
- Renaming (WIP)

### <!-- 1 -->🐛 Bug Fixes

- "transformeur" tout court.

## [2024.01.26.2] - 2024-01-26

### <!-- 0 -->🚀 Features

- Renaming + forms

## [2024.01.26.1] - 2024-01-26

### <!-- 0 -->🚀 Features

- Wip forms
- Use wtforms and try to fix form issues.
- Forms (wip)
- Newsroom + wtforms.

## [2024.01.19.1] - 2024-01-19

### <!-- 1 -->🐛 Bug Fixes

- Roles

### <!-- 2 -->🚜 Refactor

- Use enum for roles.

## [2024.01.18.2] - 2024-01-18

### <!-- 0 -->🚀 Features

- Avis d'enquete (selected d'experts)
- Wip avis d'enquete
- Geoloc & avis d'enquete.

## [2024.01.18.1] - 2024-01-18

### <!-- 0 -->🚀 Features

- Tweak css
- Tweak css

### <!-- 2 -->🚜 Refactor

- Use custom CSS classes for titles.

## [2024.01.12.1] - 2024-01-12

### <!-- 0 -->🚀 Features

- Cleanup newsroom + ciblage avis d'enquete
- Avis-enquete (ciblage)

### <!-- 1 -->🐛 Bug Fixes

- WIP CRUD
- Setup flask debug toolbar

## [2024.01.11.1] - 2024-01-11

### <!-- 2 -->🚜 Refactor

- @define -> @frozen
- Pull method up.

### <!-- 6 -->🧪 Testing

- Refact e2e tests
- Try to fix e2e tests (unsuccessfully)

## [2024.01.05.2] - 2024-01-05

### <!-- 1 -->🐛 Bug Fixes

- Don't raise error on missing component.

## [2024.01.05.1] - 2024-01-05

### <!-- 1 -->🐛 Bug Fixes

- Noxfile
- Newsroom
- Cleanup faker, fix some newsroom issues.

### <!-- 2 -->🚜 Refactor

- Use flask-super
- Use flask-super.
- Use flask-super.
- Use flask-super
- Use flask-super.
- Move generic code up the inheritance hierarchy

## [2024.01.04.1] - 2024-01-04

### <!-- 2 -->🚜 Refactor

- Cleanup

## [2023.12.22.3] - 2023-12-22

### <!-- 0 -->🚀 Features

- Forms (newsroom)

## [2023.12.22.2] - 2023-12-22

### <!-- 1 -->🐛 Bug Fixes

- Deployment error

## [2023.12.22.1] - 2023-12-22

### <!-- 1 -->🐛 Bug Fixes

- Faker, model
- Unbreak previous refactoring.

### <!-- 2 -->🚜 Refactor

- Split template
- Completely overall application setup.

## [2023.12.21.1] - 2023-12-21

### <!-- 0 -->🚀 Features

- Add sujets (+ refact forms)

### <!-- 2 -->🚜 Refactor

- Deduplicate code.
- More dedupe

## [2023.12.15.4] - 2023-12-15

### <!-- 1 -->🐛 Bug Fixes

- CSS tweaks.
- Proper name for metadata

### <!-- 2 -->🚜 Refactor

- Newsroom
- Split module.
- Custom choices.js CSS (not working better)

## [2023.12.15.3] - 2023-12-15

### <!-- 2 -->🚜 Refactor

- Forms, newsroom
- Newsroom
- Newsroom using CBVs

## [2023.12.15.2] - 2023-12-15

### <!-- 0 -->🚀 Features

- Avis d'enquete (WIP)

## [2023.12.15.1] - 2023-12-15

### <!-- 1 -->🐛 Bug Fixes

- Import openpyxl only of needed.

## [2023.12.14.1] - 2023-12-14

### <!-- 2 -->🚜 Refactor

- Taxonomies (WIP).
- Taxonomies (WIP)
- Taxonomies (WIP)
- Ontologies.

## [2023.12.12.1] - 2023-12-12

### <!-- 0 -->🚀 Features

- Remove obsolete ontologies.

## [2023.12.08.2] - 2023-12-08

### <!-- 1 -->🐛 Bug Fixes

- Temp fixes.

## [2023.12.08.1] - 2023-12-08

### <!-- 0 -->🚀 Features

- Update document (newsroom) model
- Wip document moden

## [2023.12.01.2] - 2023-12-01

### <!-- 0 -->🚀 Features

- Newsroom.

## [2023.11.23.10] - 2023-11-23

### <!-- 2 -->🚜 Refactor

- Rebane container parameter.

## [2023.11.23.6] - 2023-11-23

### <!-- 1 -->🐛 Bug Fixes

- Don't install playright

## [2023.11.23.5] - 2023-11-23

### <!-- 6 -->🧪 Testing

- Test service container.

## [2023.11.23.4] - 2023-11-23

### <!-- 1 -->🐛 Bug Fixes

- Workaround svcs bug.

## [2023.11.23.2] - 2023-11-23

### <!-- 0 -->🚀 Features

- Working on blob service.

### <!-- 1 -->🐛 Bug Fixes

- Type errors.

### Chore

- Format docstrings.

## [2023.11.23.1] - 2023-11-23

### <!-- 2 -->🚜 Refactor

- Service registration
- Services / components registration.

## [2023.11.22.3] - 2023-11-22

### <!-- 0 -->🚀 Features

- Renaming

## [2023.11.22.2] - 2023-11-22

### <!-- 1 -->🐛 Bug Fixes

- Wrong dates / date formats.

## [2023.11.22.1] - 2023-11-22

### <!-- 0 -->🚀 Features

- Work on newsroom.
- Avis d'enquetes.

### <!-- 1 -->🐛 Bug Fixes

- Date formatting.

### <!-- 2 -->🚜 Refactor

- Remove fails "controller" experiment.

### <!-- 6 -->🧪 Testing

- Test against both sqlite and postgres.

## [2023.11.16.1] - 2023-11-16

### <!-- 1 -->🐛 Bug Fixes

- Udate deps + fix typing issues.

### <!-- 2 -->🚜 Refactor

- Fix typing issues, cleanup.

### <!-- 3 -->📚 Documentation

- Try to generate diagrams (-> fail).

### <!-- 6 -->🧪 Testing

- Update deptry config.

## [2023.11.10.3] - 2023-11-10

### <!-- 1 -->🐛 Bug Fixes

- Wording.

## [2023.11.10.2] - 2023-11-10

### <!-- 1 -->🐛 Bug Fixes

- No html in summaries.

## [2023.11.10.1] - 2023-11-10

### <!-- 1 -->🐛 Bug Fixes

- Bugs on prod.

## [2023.11.09.5] - 2023-11-09

### <!-- 0 -->🚀 Features

- Tooltips on images.

### <!-- 1 -->🐛 Bug Fixes

- Vignettes.

## [2023.11.09.4] - 2023-11-09

### <!-- 0 -->🚀 Features

- Improve table design.
- CRUD articles.
- Live search w/ htmx

### <!-- 2 -->🚜 Refactor

- Simplify using a repository.
- Move files around.

### <!-- 6 -->🧪 Testing

- Cleanup / refact / add tests.
- Fix test config.

## [2023.11.09.3] - 2023-11-09

### <!-- 1 -->🐛 Bug Fixes

- Tables.

## [2023.11.09.2] - 2023-11-09

### <!-- 1 -->🐛 Bug Fixes

- Temp fix.

## [2023.11.09.1] - 2023-11-09

### <!-- 0 -->🚀 Features

- Start experimenting with flowbites tables.
- New tables.

### <!-- 1 -->🐛 Bug Fixes

- Programming error.

### <!-- 2 -->🚜 Refactor

- Various small cleanups / fixes.

### Devops

- Try Python 3.12 on heroku

## [2023.11.07.1] - 2023-11-07

### <!-- 0 -->🚀 Features

- Crud, editor.
- Forms.
- Image fields.

### <!-- 1 -->🐛 Bug Fixes

- Bad refactoring

### <!-- 2 -->🚜 Refactor

- Describe forms with Python, not TOML.
- Don't use toml for forms.

### <!-- 6 -->🧪 Testing

- 100% coverage.
- Improve test coverage.

## [2023.11.06.1] - 2023-11-06

### <!-- 0 -->🚀 Features

- Session service
- Blob service (WIP)
- Trix integration (WIP)
- Trix images.
- CRUD articles.

### <!-- 1 -->🐛 Bug Fixes

- Article form

### <!-- 2 -->🚜 Refactor

- Use CBV (WIP).
- CRUD
- Rename / cleanup.

## [2023.11.03.1] - 2023-11-03

### <!-- 0 -->🚀 Features

- Create blob service (only stubs for now).
- Experiment with flask-restful
- Work on WIP.

### <!-- 2 -->🚜 Refactor

- Put page repository in container.
- Menu in wip.

## [2023.10.30.1] - 2023-10-30

### <!-- 2 -->🚜 Refactor

- Rename templates.
- Rename method.

## [2023.10.27.1] - 2023-10-27

### <!-- 0 -->🚀 Features

- Dashboard: ajouter "articles en cours" et "articles vendus"
- Ajouter le nom du média dans la liste des publications
- Faire apparaître des cartes plutôt que des items dans les publications d'un individu

### <!-- 2 -->🚜 Refactor

- Rename function
- More explicit variable name
- Extract slider component.

## [2023.10.26.3] - 2023-10-26

### <!-- 0 -->🚀 Features

- Add a button

## [2023.10.26.2] - 2023-10-26

### <!-- 0 -->🚀 Features

- Publish articles.
- Work on publishing and dashboard.
- Onglet "publication" sur les agences et les média.
- Improve organisations tabs.
- Placeholder images.

### <!-- 1 -->🐛 Bug Fixes

- Regression on tabs.

## [2023.10.26.1] - 2023-10-26

### <!-- 0 -->🚀 Features

- Fix/improve WIP navigation.
- Publish articles.

### <!-- 1 -->🐛 Bug Fixes

- Issues found by mypy.
- WIP -> Work

### <!-- 2 -->🚜 Refactor

- Cleanup.
- Menus (SWORK)
- Use menu API + rename base classes.
- Simplify context management.
- Use match statements (instead of ifs).

## [2023.10.24.2] - 2023-10-24

### <!-- 2 -->🚜 Refactor

- Controller.
- Templateing refact (WIP).
- Use {% extends %}
- Use render_template_string
- Cleanup imports.
- Cleanup imports.
- Cleanup, reduce dependency on the page objects.

### <!-- 3 -->📚 Documentation

- Add doc on tests.

### <!-- 6 -->🧪 Testing

- Fix playwright test.

## [2023.10.24.1] - 2023-10-24

### <!-- 1 -->🐛 Bug Fixes

- DI issue.

### <!-- 2 -->🚜 Refactor

- New controller for CRUD.
- Cleanup.
- CRUD controllers.
- E2e/integration tests

## [2023.10.13.2] - 2023-10-13

### <!-- 1 -->🐛 Bug Fixes

- Https://trello.com/c/OUidNRRw/108

## [2023.10.13.1] - 2023-10-13

### <!-- 0 -->🚀 Features

- Update ontologies

## [2023.10.12.2] - 2023-10-12

### <!-- 0 -->🚀 Features

- Work on crud

### <!-- 2 -->🚜 Refactor

- Remove dependency on domonic.
- Move html utilities to "lib.html" modules.

### <!-- 6 -->🧪 Testing

- Fix e2e tests following renaming.

## [2023.10.12.1] - 2023-10-12

### <!-- 1 -->🐛 Bug Fixes

- Silence many linter warnings.

## [2023.10.06.1] - 2023-10-06

### <!-- 1 -->🐛 Bug Fixes

- Pywire bug (-> issue on filtering).

## [2023.10.05.5] - 2023-10-05

### <!-- 1 -->🐛 Bug Fixes

- Don't fail on missing attribute

### <!-- 3 -->📚 Documentation

- Db model

## [2023.10.05.2] - 2023-10-05

### <!-- 3 -->📚 Documentation

- Intégration dolibarr

## [2023.10.05.1] - 2023-10-05

### <!-- 0 -->🚀 Features

- Renaming (https://trello.com/c/wvG443sL/128-naming)

## [2023.10.04.1] - 2023-10-04

### <!-- 2 -->🚜 Refactor

- Better Screenshot service + use svcs.

## [2023.09.28.1] - 2023-09-28

### <!-- 0 -->🚀 Features

- Add "mail" page.

## [2023.09.25.1] - 2023-09-25

### <!-- 3 -->📚 Documentation

- Tweak cliff notes.

## [2023.09.22.1] - 2023-09-22

### <!-- 2 -->🚜 Refactor

- Rename policies.
- Use flask-htmx extension.
- Cleanup/fix KYC

### Tool

- Generate changelog via git-cliff.

## [2023.09.19.1] - 2023-09-19

### <!-- 0 -->🚀 Features

- ABAC policies.

## [2023.09.13.3] - 2023-09-13

### Devops

- Fix (?) heroku deploy

## [2023.09.13.1] - 2023-09-13

### <!-- 0 -->🚀 Features

- Preferences (contact)

### <!-- 2 -->🚜 Refactor

- Introduce services dependency management.
- Services.
- Screenshot service.
- Services.
- Deployment + cleanup screenshot service.

### <!-- 3 -->📚 Documentation

- Update readme.
- Tweak readme (main dependencies).

## [2023.09.07.1] - 2023-09-07

### <!-- 0 -->🚀 Features

- Update KYC forms.

## [2023.08.04.3] - 2023-08-04

### <!-- 0 -->🚀 Features

- Wtforms

## [2023.08.04.2] - 2023-08-04

### <!-- 1 -->🐛 Bug Fixes

- Fist step + stash old code.

## [2023.08.04.1] - 2023-08-04

### <!-- 0 -->🚀 Features

- Tweak KYC

### <!-- 2 -->🚜 Refactor

- Steps + fix some forms

## [2023.07.28.3] - 2023-07-28

### <!-- 0 -->🚀 Features

- Parrainages (placeholder)

## [2023.07.28.2] - 2023-07-28

### <!-- 0 -->🚀 Features

- KYC

## [2023.07.28.1] - 2023-07-28

### <!-- 0 -->🚀 Features

- KYC (refact + more cases).

### <!-- 1 -->🐛 Bug Fixes

- Circular import.

## [2023.07.21.2] - 2023-07-21

### <!-- 0 -->🚀 Features

- KYC

## [2023.07.21.1] - 2023-07-21

### <!-- 1 -->🐛 Bug Fixes

- Update KYC forms.

## [2023.07.18.1] - 2023-07-18

### <!-- 0 -->🚀 Features

- Rename / remove menu entry
- KYC (WIP)
- KYC

### <!-- 2 -->🚜 Refactor

- Debupe code in component framework.

## [2023.07.07.2] - 2023-07-07

### <!-- 1 -->🐛 Bug Fixes

- Quick fix CSP.

## [2023.07.07.1] - 2023-07-07

### <!-- 2 -->🚜 Refactor

- Document models and forms.
- Reorg domain models.

## [2023.07.06.2] - 2023-07-06

### <!-- 1 -->🐛 Bug Fixes

- Don't remove assets.

## [2023.07.06.1] - 2023-07-06

### <!-- 0 -->🚀 Features

- KYC forms (wip).

## [2023.06.29.6] - 2023-06-29

### <!-- 1 -->🐛 Bug Fixes

- Faker.

## [2023.06.29.5] - 2023-06-29

### <!-- 1 -->🐛 Bug Fixes

- Again

## [2023.06.29.4] - 2023-06-29

### <!-- 1 -->🐛 Bug Fixes

- Again

## [2023.06.29.3] - 2023-06-29

### <!-- 1 -->🐛 Bug Fixes

- CSP issue again

## [2023.06.29.2] - 2023-06-29

### <!-- 1 -->🐛 Bug Fixes

- CSP error when deployed.

## [2023.06.29.1] - 2023-06-29

### <!-- 0 -->🚀 Features

- Subscriptions (WIP).
- Content forms.
- Remove usernames.
- Iam using userfront.

## [2023.06.28.1] - 2023-06-28

### <!-- 0 -->🚀 Features

- Start work on subscriptions.
- Move "admin" menu to its own button.

## [2023.06.23.2] - 2023-06-23

### <!-- 0 -->🚀 Features

- Menu "create"

## [2023.06.23.1] - 2023-06-23

### <!-- 0 -->🚀 Features

- WIP/contents
- WIP/contents
- "rich-select"

### <!-- 2 -->🚜 Refactor

- Forms templates (wip)

## [2023.06.16.1] - 2023-06-16

### <!-- 0 -->🚀 Features

- Pages and tests
- Forms
- Forms.
- Restart work on newsroom (WIP).
- Work on newsroom.

### <!-- 1 -->🐛 Bug Fixes

- Content creation menu ("+")

### <!-- 2 -->🚜 Refactor

- Content management screens.
- Move some methods up the class hierarchy.
- Split form package.
- Forms.

### <!-- 6 -->🧪 Testing

- Cleanup / refactor.

## [2023.06.14.1] - 2023-06-14

### Wip

- Try to fix splinter tests

## [2023.06.12.3] - 2023-06-12

### <!-- 2 -->🚜 Refactor

- Update flask API

## [2023.06.12.2] - 2023-06-12

### <!-- 1 -->🐛 Bug Fixes

- Temp workaround for Heroku failure.

## [2023.06.05.3] - 2023-06-05

### <!-- 1 -->🐛 Bug Fixes

- Forgot to compile assets once again.

## [2023.06.05.2] - 2023-06-05

### <!-- 0 -->🚀 Features

- Export ontologies.

## [2023.06.05.1] - 2023-06-05

### <!-- 1 -->🐛 Bug Fixes

- Remove log when call from CLI + add "components" CLI command.

## [2023.05.26.2] - 2023-05-26

### <!-- 1 -->🐛 Bug Fixes

- Forgot assets (once more).

## [2023.05.26.1] - 2023-05-26

### <!-- 0 -->🚀 Features

- Work on contents backoffice.
- Content management.

## [2023.05.25.3] - 2023-05-25

### <!-- 2 -->🚜 Refactor

- Datatables.
- Datatables.

## [2023.05.25.2] - 2023-05-25

### <!-- 0 -->🚀 Features

- Use datatable component for contents view.

## [2023.05.25.1] - 2023-05-25

### <!-- 0 -->🚀 Features

- WIP dashboard.

## [2023.05.24.1] - 2023-05-24

### Nua

- Correct debian dependencies.

## [2023.05.17.4] - 2023-05-17

### <!-- 1 -->🐛 Bug Fixes

- CSP config

## [2023.05.17.1] - 2023-05-17

### <!-- 0 -->🚀 Features

- Add tracking by shynet.

## [2023.05.15.5] - 2023-05-15

### <!-- 1 -->🐛 Bug Fixes

- We still must build the assets.

## [2023.05.15.4] - 2023-05-15

### <!-- 0 -->🚀 Features

- Better dashboard integration (can be easily secured).

## [2023.05.15.3] - 2023-05-15

### <!-- 1 -->🐛 Bug Fixes

- Change initialisation order.

## [2023.05.15.2] - 2023-05-15

### <!-- 0 -->🚀 Features

- Mount Dramtiq dashboard on /drama/

### Chore

- Update deps

## [2023.05.15.1] - 2023-05-15

### <!-- 1 -->🐛 Bug Fixes

- Redis config on heroku.

## [2023.05.12.3] - 2023-05-12

### <!-- 1 -->🐛 Bug Fixes

- Loguru error on prod.

## [2023.05.12.2] - 2023-05-12

### <!-- 1 -->🐛 Bug Fixes

- Remove old rq-based tasks.

## [2023.05.12.1] - 2023-05-12

### <!-- 0 -->🚀 Features

- Start work on transactional emails.
- Finish Dramatiq integration.

### <!-- 2 -->🚜 Refactor

- Try to use Dramatiq instead of RQ.
- Components / services registration via dedicated signal.

## [2023.05.11.3] - 2023-05-11

### <!-- 1 -->🐛 Bug Fixes

- Mail = back to Gandi.

## [2023.05.11.1] - 2023-05-11

### <!-- 1 -->🐛 Bug Fixes

- Fix some warnings.
- Fix registration and replace flask-mailing by flask-mailman.

## [2023.05.05.1] - 2023-05-05

### <!-- 8 -->◀️ Revert

- Use a working email address.

## [2023.05.04.4] - 2023-05-04

### Config

- Tweak settings.

## [2023.05.04.2] - 2023-05-04

### <!-- 1 -->🐛 Bug Fixes

- Prebuild vite assets because fuck heroku
- Tweak text.

## [2023.05.04.1] - 2023-05-04

### <!-- 1 -->🐛 Bug Fixes

- Typing issues on search.

## [2023.05.02.1] - 2023-05-02

### <!-- 0 -->🚀 Features

- Only show "european" languages.
- KYC et WIP.

## [2023.04.27.3] - 2023-04-27

### <!-- 0 -->🚀 Features

- Forms.

## [2023.04.27.2] - 2023-04-27

### <!-- 1 -->🐛 Bug Fixes

- Adt bump-version no longer has `--rule` option.

## [2023.04.21.1] - 2023-04-21

### <!-- 0 -->🚀 Features

- Menu component (WIP).
- KYC wizard.

## [2023.04.19.3] - 2023-04-19

### <!-- 0 -->🚀 Features

- Renaming.

## [2023.04.19.2] - 2023-04-19

### <!-- 0 -->🚀 Features

- Wire des communiqués sur le business wall.

### <!-- 1 -->🐛 Bug Fixes

- Workaround redis issue.

### <!-- 2 -->🚜 Refactor

- Components framework (WIP).
- Move common components to a "common" module.

## [2023.04.14.1] - 2023-04-14

### <!-- 0 -->🚀 Features

- Tweak business wall.
- Start work on KYC.
- Start of KYC.
- KYC
- KYC

### <!-- 1 -->🐛 Bug Fixes

- Workaround weasyprint installation issue is some cases.

### Devops

- Nua config.
- Deploy using Nua (WIP).
- Nua config (WIP).

## [2023.04.07.2] - 2023-04-07

### <!-- 0 -->🚀 Features

- Business wall.

## [2023.04.07.1] - 2023-04-07

### <!-- 0 -->🚀 Features

- Remove info (as requested by customer).
- "fake news" generator.
- Screenshoting (not working yet)
- Tweak design of business wall.

### <!-- 1 -->🐛 Bug Fixes

- Route was not declared.

### <!-- 6 -->🧪 Testing

- Make playright test parametrizable by base-url.
- Work on e2e tests.

### Devops

- Try to build with Nua (not working).

## [2023.03.31.3] - 2023-03-31

### <!-- 0 -->🚀 Features

- Business wall.

## [2023.03.31.2] - 2023-03-31

### <!-- 6 -->🧪 Testing

- E2e tests.

## [2023.03.31.1] - 2023-03-31

### <!-- 6 -->🧪 Testing

- Introduce Playwright e2e tests.

## [2023.03.30.1] - 2023-03-30

### <!-- 0 -->🚀 Features

- Get version.
- Start work on blob storage and web content.

### <!-- 2 -->🚜 Refactor

- Cleanup org model and add new field.

### <!-- 6 -->🧪 Testing

- Test against Postgres, not SQLite.

### AI

- Experimenting with Gensim.

### Feat

- Business wall.

## [2023.03.24.1] - 2023-03-24

### <!-- 0 -->🚀 Features

- Start work on stats.
- Compute stats.
- Stats (UI)
- Tweak stats module.

## [2023.03.23.1] - 2023-03-23

### <!-- 0 -->🚀 Features

- Tweak invoice model.
- "performance" -> "performance réputationnelle".
- Admin/contents.
- Admin/transactions.
- Generate transaction and display them better.

### <!-- 1 -->🐛 Bug Fixes

- Tweak CSS.

### <!-- 2 -->🚜 Refactor

- Html generation (not ready yet).
- Refact backoffice, add transactions.
- Admin module.

## [2023.03.21.1] - 2023-03-21

### <!-- 0 -->🚀 Features

- Start work on mailer.

### <!-- 2 -->🚜 Refactor

- Replace ad-hoc scanner with Venusian.
- Move "register_macros" to main
- Use lookups instead of ad-hoc registration.
- Introduce common lib for IOC.

### <!-- 6 -->🧪 Testing

- Fix noxfile.

## [2023.03.16.4] - 2023-03-16

### <!-- 1 -->🐛 Bug Fixes

- Use more compressed archive of nodejs

## [2023.03.16.2] - 2023-03-16

### <!-- 1 -->🐛 Bug Fixes

- Missing dependency on weasyprint

## [2023.03.16.1] - 2023-03-16

### <!-- 0 -->🚀 Features

- Start work on invoices.
- Billing UI.
- Generate PDF invoices.

### <!-- 2 -->🚜 Refactor

- Cleanup / split WIP module.

### <!-- 6 -->🧪 Testing

- Properly test invoices (WIP).

## [2023.03.15.2] - 2023-03-15

### <!-- 0 -->🚀 Features

- Add publisher to posts.
- Add publisher.

## [2023.03.12.1] - 2023-03-12

### <!-- 1 -->🐛 Bug Fixes

- Deps + try do deal with email error.

## [2023.03.11.1] - 2023-03-11

### <!-- 1 -->🐛 Bug Fixes

- Reputation

## [2023.03.10.9] - 2023-03-10

### <!-- 1 -->🐛 Bug Fixes

- Forgot to commit migration

## [2023.03.10.7] - 2023-03-10

### <!-- 1 -->🐛 Bug Fixes

- Whoa, mypy found an actual, hard to find, bug.

### <!-- 2 -->🚜 Refactor

- Use/improve "class Meta".

## [2023.03.10.6] - 2023-03-10

### <!-- 0 -->🚀 Features

- Randomize reputation (a bit)

## [2023.03.10.4] - 2023-03-10

### <!-- 1 -->🐛 Bug Fixes

- Prod requirements.

## [2023.03.10.1] - 2023-03-10

### <!-- 0 -->🚀 Features

- Publication status + transaction dashboard

## [2023.03.09.7] - 2023-03-09

### <!-- 0 -->🚀 Features

- Start work on wallets and transactions.

### <!-- 2 -->🚜 Refactor

- Isolate faker.

## [2023.03.09.6] - 2023-03-09

### <!-- 2 -->🚜 Refactor

- Cleanup.

## [2023.03.09.3] - 2023-03-09

### <!-- 0 -->🚀 Features

- Send emails (using flask-mailing).

## [2023.03.09.2] - 2023-03-09

### <!-- 0 -->🚀 Features

- Working on queues.
- Show real reputation.

### <!-- 1 -->🐛 Bug Fixes

- Wakaq extension.

## [2023.03.09.1] - 2023-03-09

### <!-- 0 -->🚀 Features

- RQ integration.

## [2023.03.08.9] - 2023-03-08

### <!-- 2 -->🚜 Refactor

- Remove dependencies.

## [2023.03.08.7] - 2023-03-08

### Devops

- Another tweak for heroku

## [2023.03.08.3] - 2023-03-08

### Devops

- Heroku config

## [2023.03.08.2] - 2023-03-08

### Devops

- Use Python 3.11 on Heroku.

## [2023.03.08.1] - 2023-03-08

### <!-- 0 -->🚀 Features

- Roles (WIP, just started).
- Wallet model (WIP).
- Fix / add features and tests to tagging service.
- Work on activity streams.
- Tracking service.
- Start (re)working on roles.
- Add a snowflake id generator.
- Add "base62" functions.
- Reputation history
- Reputation (WIP).
- Reputation.

### <!-- 1 -->🐛 Bug Fixes

- Wallet model.
- Remove duplicate column
- Bug with components  labels.

### <!-- 2 -->🚜 Refactor

- Rename 'apps' -> 'modules'.
- Move models closer to theyr usage.
- Move models around again.
- Social graph.
- Finish social graph refactoring.
- Make events module more self contained.
- Services & tests
- Reput.
- Adapters.
- Rename test files.
- Don't use aenum anymore.
- Pages.
- Cleanup / use loguru.
- Page registration via decorators.
- Finish cleanup of page registration.
- Hide internal implementation for reputation.
- Use the updated interfaces / services.
- Reputation (hide implem).
- Move module around.
- Move modules around
- Move models around.
- Use enum for publication lifecycle.
- Group "pywire" modules together (WIP).
- Move modules around.
- Move pywore module around again.
- Rework content model.
- Update for SQLAlchemy 2.0 compatibility (using the old API).
- SQLA 2.0 API.
- SQLA 2.0
- SQLA 2.0
- SQLA 2.0
- Cleanup post SQLA 2.0.
- Cleanup data model.
- SQLA 2.0
- Cleanup.
- Use generated "snowflake ids".
- Encode ids.

### <!-- 6 -->🧪 Testing

- Fix deptry config.
- Add architecture tests

### Deps

- Replace flask-babelex by flask-babel.

## [2023.02.17.2] - 2023-02-17

### <!-- 0 -->🚀 Features

- Reput

## [2023.02.17.1] - 2023-02-17

### <!-- 0 -->🚀 Features

- Late-night work on superadmin (WIP)

## [2023.02.16.2] - 2023-02-16

### <!-- 0 -->🚀 Features

- Add rule engine for admin UI.

## [2023.02.15.1] - 2023-02-15

### <!-- 0 -->🚀 Features

- Prototype "superadmin" app.
- Proto admin

### <!-- 2 -->🚜 Refactor

- Use SQLA2 API.
- More SQLA2 cosmits.

## [2023.02.13.2] - 2023-02-13

### <!-- 2 -->🚜 Refactor

- Vendorize livewire.

## [2023.02.13.1] - 2023-02-13

### <!-- 2 -->🚜 Refactor

- Refact / cleanup front-end code.
- Cleanup livewire & alpine-components.

### WIP

- New / alternative admin.

### Wording

- Reputation -> performance.

## [2023.02.10.1] - 2023-02-10

### <!-- 0 -->🚀 Features

- Karma + admin

## [2023.02.09.1] - 2023-02-09

### <!-- 1 -->🐛 Bug Fixes

- Icons issues + tweak footer.

## [2023.02.03.3] - 2023-02-03

### <!-- 0 -->🚀 Features

- Mockup com'room.

## [2023.02.03.1] - 2023-02-02

### <!-- 0 -->🚀 Features

- Implémentation des specs des Com'Room (WIP).

### <!-- 2 -->🚜 Refactor

- Rename classes, cleanup a bit.
- Move template to a generic directory.

## [2023.02.02.1] - 2023-02-02

### WIP

- Working on tables.

## [2023.01.26.3] - 2023-01-26

### Wording

- Formations -> webinars.

## [2023.01.20.1] - 2023-01-20

### <!-- 0 -->🚀 Features

- Work on reputation / performance.
- Newsroom (wip).
- Newsroom (wip)

### <!-- 2 -->🚜 Refactor

- Use better JSON type.
- Import table as t.

## [2023.01.17.5] - 2023-01-17

### <!-- 0 -->🚀 Features

- Proto newsroom.
- Tweak WIP menu.

### <!-- 1 -->🐛 Bug Fixes

- Lint warnings.

### <!-- 2 -->🚜 Refactor

- Convert doit script to invoke.

### Ci

- Fix tox issues.
- Make lint

### Devops

- Nua config.

## [2023.01.06.1] - 2023-01-06

### <!-- 0 -->🚀 Features

- Add rq.
- Work on search.
- Search.
- Delegation (WIP).

### <!-- 1 -->🐛 Bug Fixes

- Css fix for search page.

### <!-- 3 -->📚 Documentation

- Update README

### Cloud

- Still tweaking heroku deployment.

## [2022.12.22.1] - 2022-12-22

### <!-- 0 -->🚀 Features

- Generate static files on startup.
- Marketing content.

### <!-- 1 -->🐛 Bug Fixes

- Missing deps.
- Add missing markdown dependency.
- Try workaround to get npm.

### Devops

- Heroku runtime.

## [2022.12.21.1] - 2022-12-21

### <!-- 0 -->🚀 Features

- Start using Typesense.
- Use typesense.
- Add footer + use loguru for proper logs.
- Public pages.

### <!-- 1 -->🐛 Bug Fixes

- Add missing temp logo.

## [2022.11.28.3] - 2022-11-28

### <!-- 1 -->🐛 Bug Fixes

- Workaround filter bugs.

## [2022.11.28.1] - 2022-11-27

### <!-- 0 -->🚀 Features

- Front-end integration.
- Integration front-end
- Start data model, testing.
- Wire pages.
- Checkpoint integration front/back.
- Work on data model.
- Deploy, wip back end.
- Wip profile.
- Start events, cleanup fake data.
- Wire, profile.
- WIP.
- WIP page.
- Events.
- Docker.
- Dockerize.
- Work on search.
- Wip.
- Docker + events.
- Better timestamps.
- Tooltips.
- Admin UI (WIP) + refact DB model.
- Model.
- Workaround ORM modeling issues + add features.
- More fakers.
- Pricing page.
- WIP data model.
- Tabs.
- Add some settings / master data.
- Pages.
- Add POST request handling.
- Start work on social graph.
- Likes.
- Work on templates.
- Annuaire des organisations (WIP).
- Tabs.
- Tweak design
- Events.
- Wip.
- Wip
- Wip.
- Article.
- Comments.
- Préférences.
- Opengraph, schema.org, events.
- Halo autour des profils.
- Groups.
- Group.
- Comment counts.
- WIP.
- View tracker.
- Generate logos.
- Tweak presentation + add image service.
- Wip.
- Work on vocabularies.
- Add reference data.
- WIP.
- Pitch model.
- WIP.
- Tweak colors.
- Parsing Wikinews + NLP/NER.
- Generate press releases.
- Work on wire. Also refactor content model.
- Annuaire org.
- Tweaks.
- Tags.
- Start work on filtering.
- Preference.
- Top header.
- UX
- Wire page.
- Add dashboard mockup + refact.
- Improve WIP.
- UX
- Introduce simple tables.
- WIP pages.
- Work on WIP.
- Start work on roles.
- Simple login.
- WIP.
- Tweak roles, demo.
- Convert macro to domonic.
- Sort & selection on wire.
- Work on wire filters.
- Small changes following today's meeting.
- Followers / followees (WIP).
- Followers / followees.
- Posts.
- Ajout des hobbies.
- Toaster (WIP).
- Fake calendar
- Article creation form.
- Design events.
- Authentication (via Flask Security).
- Ui for security.
- Backoffice.
- Event calendar
- Calendar view.
- POC datatable.
- Put item back on the menue.
- Tweak events design.
- Biz.
- WIP biz.
- Biz
- BIZ
- Wip BIZ + refacto ui components.
- Tweak design for events.
- Events
- Events.
- WIP events.
- Add promotion boxes.
- Design BIZ.
- Display press releases (Wire).
- Add trix editor.
- Rich-text fields (using Trix).
- Use quill.
- Work woth heroku
- Better design.
- Design
- Tweak UI
- Promo boxes on swork.
- Work on SWORK templates.
- Likes on SWORK posts.
- Work on the Wire page.
- Trending posts.
- Nav on categories (WIP).
- Work on UI.
- Work on evants.
- Tweak events
- Tweak events.
- Tabs on events.
- Selectors for member directory.
- 1rst page of new specs.
- Following (extended to orgs).
- Onglet "Wire / Medias"
- Wip notes d'Erick.
- Following/leaving groups.
- Activity streams.
- Work on timelines.
- Filters (wip)
- Filtering by tag.
- Filters (wip)
- Filters.
- Filters.
- Restart work on search.
- Tweak base API.
- Search (wip)
- Reactivate Talisman.
- Search
- Tweak FTS.
- Expand search scope.
- Improve search UI.
- More search classes.
- Work on WIP.
- Create docs (wip).
- Directories & filters.
- Addresses (WIP).
- More addressable stuff.
- Make users adressable.
- Geoloc (WIP).
- Geo loc.
- Pages non-officielles + filtrage des orgs.
- Filters, boosting.
- Htmx cleanup + filtering on events.
- Events.
- Event participation.
- Wip upgrade profil corporate.
- Use lifewire for filtering.
- Filters (WIP).
- Sowkr filters.
- Better looking calendar
- Geoloc.
- Recherche par CP.
- CPPAP / SAPI / ...
- Proper naming for publisher.
- Chaneg position of badges.
- Stripe payments.
- Pages entreprises.
- Better icons.
- Tweak text width.
- Icons (WIP).
- Search, groups.

### <!-- 1 -->🐛 Bug Fixes

- Workaround typing issue.
- Fix tests.
- Route issue.
- Bug with ORM model.
- UI was broken.
- Tailwind must find all templates.
- Previous commit.
- Db schema issue revealed by PostgreSQL
- Fix small bugs.
- Marketplace urls.
- Transaction issue.
- Database url
- Auth issue.
- SQLAlchemy model issues.
- SWORK search issue.
- Search bar design issues.
- Event calendar.
- Change wording.
- Remove webargs warning.
- Don't use server side sessions for now
- Redirect to default tab.
- Sorting bug.
- Generate random events.
- Pin opencv2 to fix build on heroku.
- Workaround cookie issue.
- Tweak swork
- Proper filtering.
- UI issue on rich text fields.
- Imports.
- Bug events.
- Tests, lints.
- Revert deps update.
- Button size.
- Calendar (filter by active tabs).
- Build tailwind (for cloud deploy).
- Refactoring error.
- Use alpinejs/focus properly.
- Missing js blob.
- Buggy filter.
- "AiPRESS24"
- Publisher for PR.
- Tooltip.
- Deps.
- Env var name.
- Template error.
- Correct imports.
- There typing packages are counter-productive.
- This seems to work now.
- Workaround Alpinejs issue.

### <!-- 2 -->🚜 Refactor

- Cleanup and reintroduce public blueprint.
- Cleanup.
- Introduce 'private' blueprint.
- Use enum to classify content types.
- Remove demo home.
- Introduce pendulum, cleanup.
- Use jinja as it's faster that lxml XML generation.
- Joined table model inheritance.
- Content model.
- Mote templates to server side (WIP).
- New blueprint.
- Modularise.
- Viewmodels.
- Remove Vuejs front-end.
- Work on templates.
- Use venusian to scan blueprints.
- Preferences.
- Refactor menus.
- Cleanup imports.
- Mouve routes closer to their pages.
- Improve sqla2uml output.
- Introduce '@page' annotation.
- Rename vm -> view_model.
- Ensure ORM model is independent from web layer.
- Split module.
- Pendulum -> arrow + update
- Use Werkzeug's module scanner instead of Venusian.
- Use htmx for tabs.
- CSS prose -> content.
- Format templates.
- Serve assets ourselves.
- Introduce components.
- Remove cruft
- Cleanup cruft.
- Introduce more components.
- Typing config + fix.
- Cleanup (using shed).
- Cleanup components.
- Remove temp hack.
- Remove hack.
- Cleanup imports.
- Templates.
- Use falsk-vite.
- Perf work.
- Better use of SQLAlchemy.
- Promo boxes.
- Change naming convention for templates.
- Menu for SWORK.
- Wires / tabs.
- Wires suite.
- Organise CSS / tailwind code.
- FTS.
- Search.
- Remove unneeded code (search).
- Format.
- Remove unneeded (and buggy) "flask dev" command.
- Introduce date filter for event calendar.
- Split template.
- Introduce wired components.
- Use pywire.
- Pywire.
- Use pywire.
- Pywire.
- Wired components.
- Selectors and swork.
- Use base class.
- Cleanup filters on SWORK.
- Use template method pattern.
- Cleanup.
- SQLAlchemy tweaks.
- Data model.

### <!-- 3 -->📚 Documentation

- Add doc.
- Update.
- Change color palette.
- Tweak pdf config.
- Update diagrams.
- Add state diagram.
- Update diagrams.

### <!-- 6 -->🧪 Testing

- Fix / add tests.
- Add some tests.
- More tests.
- Add Behaving + first test case.
- Splinter test template (not working).
- Faster test_faker.
- Refact e2e tests.
- Fix behave tests.

### Feat

- New datatable.

### WIP

- Datatables.
- Datatable.
- Forms.
- Swork (groups)

### Chode

- Cleanup.
- Deps.

### Ci

- Add tox config.
- Fix tox config.
- Fix for YAML issue.
- Tweak again.
- Tweak again
- Tweak.

### Debug

- Add debug toolbar.
- Config.

### Deps

- Use mypy from git.
- Add typeguard.
- Upgrade JS deps.
- Update poetry lock.

### Devops

- Deploy on Clever Cloud.
- Fix issue on PaaS.
- Deploy DB to Clever.
- Tweak vagrant (doesn't work).

### Heroku

- Add runtime.
- Runtime
- Try to bypass the installation issue.
- Add vite assets.
- Fix database URL.
- Add tailwind assets.
- Add static stuff (temporarily)
- More workers (?)

### Ops

- Deps + docker
- Better choice of dependencies.
- Docker script.
- Don't install dev dependencies on prod.

### Tool

- Improve diagram generator.

### Tooling

- Docker.
- Use pyanalyse.
- Use import-linter.
- Produce UML diagrams.
- Scan all the model classes.

### Tweak

- Link color for calendar.

### Ui

- Swork design.
- Update BIZ home page + cleanup.

### Wip

- Creation forms.
- Selector component.

<!-- generated by git-cliff -->
