# Changelog

All notable changes to this project will be documented in this file.

## [unreleased]

### 🧪 Testing

- PIL works better with a real cat image.

### ⚙️ Miscellaneous Tasks

- Tweak deployment (hop3)
- Tweak deployment
- Update changelog

## [2024.06.26.4] - 2024-06-26

### 🐛 Bug Fixes

- Do not use embeded base64 image for synthesis (wip)

### 🚜 Refactor

- Resize provided photos

### 🧪 Testing

- Add e2e test using playwright
- Cleanup e2e tests.
- Fix e2e file upload.
- Fix e2e tests

### ⚙️ Miscellaneous Tasks

- Update changelog
- Update changelog
- Update changelog
- Update changelog
- Update changelog

### Ui

- Better looking recap page.

## [2024.06.25.2] - 2024-06-25

### 🚀 Features

- Add mandatory GCU validation

### 🚜 Refactor

- Better display of synthesis with profile label and subtitles
- Display photos in synthesis

### ⚙️ Miscellaneous Tasks

- Apply ruff check
- Update changelog

## [2024.06.25.1] - 2024-06-25

### 🐛 Bug Fixes

- Database create_all() still requires loading of classes
- On synthesis page, "Annuler" button bg collor set to orange
- Remove debug alert()
- Set orange to be expected orange
- Size of image preview set to 128x128
- Add border around "Vos renseignements..."
- Restore the kyc .xls
- Set updated values in kyc .xls
- Styling second mail error message like the standard one

### 🚜 Refactor

- Move to flask-security for User class, follow flask-security guidelines for initialization, force bcrypt v4.0.1, remove deprecated custom salt_password (use bcrypt), rename 'email_pro' field to 'email', rename salt password fields to 'password', get closer to code organization of AIPress, try to merge flask_security User definition, WIP
- Detect unicity of email (wip)
- Add email validation against already used in DB
- Enforce that new users are not valid until validation

### ⚙️ Miscellaneous Tasks

- Vite update
- Update changelog

### Debug

- Use a debug version of MVP-2-KYC-Commons-22_dev.xlsx

## [2024.06.20.1] - 2024-06-20

### 🚜 Refactor

- Change label for email pro to "connexion email..."

### ⚙️ Miscellaneous Tasks

- Nix support
- Add dependencies: flask-security-too, bcrypt
- Update changelog

## [2024.06.18.1] - 2024-06-18

### 🐛 Bug Fixes

- Keep former photos when going back from synthesis
- Put again original MVP-2-KYC-Commons-22_dev.xlsx

### 🚜 Refactor

- Max_image_size as a parameter
- Store photos with base64 encoding

### ⚙️ Miscellaneous Tasks

- Update changelog

## [2024.06.16.1] - 2024-06-16

### 🐛 Bug Fixes

- Fix profile title in models/MVP-2-KYC-Commons-22_dev.xlsx

### ⚙️ Miscellaneous Tasks

- Cleanup changelog
- Update deps
- Update changelog

## [2024.06.13.2] - 2024-06-13

### ⚙️ Miscellaneous Tasks

- Update changelog

## [2024.06.13.1] - 2024-06-13

### 🚀 Features

- Add better file loader

### 🐛 Bug Fixes

- Load from unvalidated form (wip)
- Form modification after submit working
- Set labels Valider/Précédent/Annuler
- Fix upload image display
- Limite image size to 2MB

### 🚜 Refactor

- Split KYCUser with KYCProfile table, add dates and validation flags
- Temporay store the photo file in a dedicated table before validation and final storage
- Remove unused packages (pycountry, flask_session, cachelib)
- Add temporary_blob.py to manage temp storage of blob
- Form modification (wip)
- Refactor dynform and apply ruff & isort

### 🧪 Testing

- Add test for tmp_blob

## [2024.06.06.3] - 2024-06-06

### ⚙️ Miscellaneous Tasks

- Update changelog

## [2024.06.06.1] - 2024-06-06

### 🚀 Features

- Add "transformations majeures" question
- Mapping on DB (wip)
- Mapping on DB (wip)
- Use salted password in DB

### 🐛 Bug Fixes

- Rename email_perso -> E-mail de secours, add upper message possibility for forms, change "metiers" label and profiles
- Update profiles of group academics
- Update facteurs de match-making / press et médias
- Update profile dirigeant d une école de journalisme
- Rename fiel type_presse_&_media -> type_presse_et_media
- Use db.session from flask_sqlalchemy
- Sqlite db sometimes not detected, fix ? add flag DEBUG_USE_DB

### 🚜 Refactor

- Rename fields "*-2" -> "*_detail"
- DB uses JSON type for info_pro, match_makin, hobbies and business_wall fields
- Remove the unused module app/geonames
- Apply ruff

### 🧪 Testing

- Update ontologies, some pb on ontologies (several unicity, profession_fonction_public)
- Add test for ontology "transformation_majeure""
- Fixes for ontology 33
- Fixes for ontology 34

### ⚙️ Miscellaneous Tasks

- Update changelog

### Add

- New salted_password() and check_password() base function

## [2024.05.31.5] - 2024-05-31

### 🐛 Bug Fixes

- Update model, move column "Directeur d ecole", add field email_perso, rename field email->email_pro
- Allow more characteurs for password

### 🚜 Refactor

- Change zip/cities value code, generalize value->label conversion

### 🧪 Testing

- Update ontology test (still 3 fails on unicity)
- Adapt test_field_name() to new format
- Adapt test_ontology_json() to new format

### ⚙️ Miscellaneous Tasks

- Update changelog
- Fix deploy script
- Update changelog

## [2024.05.31.4] - 2024-05-31

### ⚙️ Miscellaneous Tasks

- Deploy task
- Update changelog

## [2024.05.31.2] - 2024-05-31

### ⚙️ Miscellaneous Tasks

- Deployment task

## [2024.05.31.1] - 2024-05-31

### 🐛 Bug Fixes

- Change "newsrooms" format to "media name (media type)" to aim unicity
- Actually update to ontologies v29
- Add "photo carte presse" and number to some journalist case
- Change list_type_agences_rp -> multi_type_agences_rp
- "secteurs d activité couverts par"
- Add function label_from_value_list() for better display of synthesis

### 🧪 Testing

- Update tests of ontologies
- Comment about bug / ontology metier
- Add test on unicity of list values for selects (4 fails)
- Update tests, let activate again test_metier() unicity error

## [2024.05.29.1] - 2024-05-29

### 🐛 Bug Fixes

- Password widget now allow to see/hide clear text password
- Fct du journalisme -> multi choices, modify llabel for "taille salariés"
- For "dirigeant agence RP", remove "Nom du groupe, ministère, de l’administration publique ou de la fédération"
- Thematiques -> centres d'interet
- Secteurs d'activite / detaillé -> par votre media / dans lequel
- Secteurs -> sous secteurs
- Textarea size to 1500 + label
- Display accepted photo formats
- "validée" -> "validée."
- Famille de métiers -> Quels métiers exercez-vous ?
- Remove trigger, fix "prorata"
- Isort ontology_select.py
- Fix some trigger message, add specific trigger message for "RP independant", not adding "cliquez ici", probably all messages need review
- Synthesis, add "Si vous validez..."
- Add more tags to TAG_LABELS for stripping labels at validation stage
- Use models/MVP-2-KYC-Commons-17_dev.xlsx
- Replace Fonctions -> Positions
- Jusqu’à combien de salariés votre organisation compte-t-elle ?
- Add line "Nom du média institutionnel"
- KYC-commeons, remove "Nom du groupe..." for "média instit"
- KYC-commeons "directeurs.rices des relations de presse ou de la communication" remove -> "Nom du groupe de relations presse ou de communication"
- Type d organisation -> dual select field
- Do not show hints on mandatory fiekds after 3rd screen, then also remove top buttons
- Allow <strong> tag for boolean field label
- Update display of somme "trigger" fields
- Add "safe" flag for label display in sunthesys (for <strong> tag)
- Update ontologies from Ontologies-27.xlsx (école de journalisme)

### 🚜 Refactor

- Compute early value/label pairs for ontologies (wip)
- Add dual computation to early value/label pairs for dual ontologies
- New early select value/pairs ready (but not used)
- Rename "thematiques_*" to "interet_*" in files
- Apply script of pre-generation of value/label pairs (without tests upgrade)

### 🧪 Testing

- Fix test_medias()
- Fix test_media_type()
- Fix test_journalisme_fonction
- Fix test_type_agence_rp()
- Fix tests for interet_politique interet_orga interet_asso

### ⚙️ Miscellaneous Tasks

- Format
- Remove unneeded imports

## [2024.05.23.1] - 2024-05-23

### 🚀 Features

- Geoloc demo.

### 🐛 Bug Fixes

- Flip order of (*) and (plusieurs choix possibles)
- Remove ununsed files

### 🚜 Refactor

- Add some "Loading" indicator while country are loading with ajax
- Split select_one widget
- Split select_one_free widget
- Split select_multi_simple widget
- Split select_multi_optgroup widget
- Split select_multi_simple_free widget

### ⚙️ Miscellaneous Tasks

- Update deps, version
- Deps

### Refact

- Use scvs flask integration.

## [0.1.1] - 2024-04-25

### 🚀 Features

- Tweak CSS

### 🐛 Bug Fixes

- Remove Step class from view.py
- Boolean field is always optionnal
- "OSError: [Errno 90] Message too long" on Linux
- Same issue.

### ⚙️ Miscellaneous Tasks

- Update deps (+ test slack webhook)
- Deps
- Tweak lint config
- Rebuild assets
- Update deps + fix ruff warnings
- Sort deps
- Format
- Update deps

### Add

- La photo d'Erick

### Debug

- Show missing Field types

### Prevalidation

- Show field required empty when going next page

### Refact

- Extract common parts of templates.
- Cleanup JS code
- Cleanup and fix typing issues.

<!-- generated by git-cliff -->
