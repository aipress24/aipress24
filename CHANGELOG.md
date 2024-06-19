# Changelog

All notable changes to this project will be documented in this file.

## [2023.09.22.1] - 2023-09-22

### Refactor

- Rename policies.
- Use flask-htmx extension.
- Cleanup/fix KYC

### Tool

- Generate changelog via git-cliff.

## [2023.09.19.1] - 2023-09-19

### Features

- ABAC policies.

## [2023.09.13.3] - 2023-09-13

### Devops

- Fix (?) heroku deploy

## [2023.09.13.1] - 2023-09-13

### Documentation

- Update readme.
- Tweak readme (main dependencies).

### Features

- Preferences (contact)

### Refactor

- Introduce services dependency management.
- Screenshot service.
- Deployment + cleanup screenshot service.

## [2023.09.07.1] - 2023-09-07

### Features

- Update KYC forms.

## [2023.08.04.3] - 2023-08-04

### Features

- Wtforms

## [2023.08.04.2] - 2023-08-04

### Bug Fixes

- Fist step + stash old code.

## [2023.08.04.1] - 2023-08-04

### Features

- Tweak KYC

### Refactor

- Steps + fix some forms

## [2023.07.28.3] - 2023-07-28

### Features

- Parrainages (placeholder)

## [2023.07.28.2] - 2023-07-28

### Features

- KYC

## [2023.07.28.1] - 2023-07-28

### Bug Fixes

- Circular import.

### Features

- KYC (refact + more cases).

## [2023.07.21.2] - 2023-07-21

### Features

- KYC

## [2023.07.21.1] - 2023-07-21

### Bug Fixes

- Update KYC forms.

## [2023.07.18.1] - 2023-07-18

### Features

- Rename / remove menu entry
- KYC

### Refactor

- Debupe code in component framework.

## [2023.07.07.2] - 2023-07-07

### Bug Fixes

- Quick fix CSP.

## [2023.07.07.1] - 2023-07-07

### Refactor

- Document models and forms.
- Reorg domain models.

## [2023.07.06.2] - 2023-07-06

### Bug Fixes

- Don't remove assets.

## [2023.07.06.1] - 2023-07-06

### Features

- KYC forms (wip).

## [2023.06.29.6] - 2023-06-29

### Bug Fixes

- Faker.

## [2023.06.29.5] - 2023-06-29

### Bug Fixes

- Again

## [2023.06.29.4] - 2023-06-29

### Bug Fixes

- Again

## [2023.06.29.3] - 2023-06-29

### Bug Fixes

- CSP issue again

## [2023.06.29.2] - 2023-06-29

### Bug Fixes

- CSP error when deployed.

## [2023.06.29.1] - 2023-06-29

### Features

- Subscriptions (WIP).
- Content forms.
- Remove usernames.
- Iam using userfront.

## [2023.06.28.1] - 2023-06-28

### Features

- Start work on subscriptions.
- Move "admin" menu to its own button.

## [2023.06.23.2] - 2023-06-23

### Features

- Menu "create"

## [2023.06.23.1] - 2023-06-23

### Features

- WIP/contents
- "rich-select"

### Refactor

- Forms templates (wip)

## [2023.06.16.1] - 2023-06-16

### Bug Fixes

- Content creation menu ("+")

### Features

- Pages and tests
- Forms.
- Restart work on newsroom (WIP).
- Work on newsroom.

### Refactor

- Content management screens.
- Move some methods up the class hierarchy.
- Split form package.
- Forms.

### Testing

- Cleanup / refactor.

## [2023.06.14.1] - 2023-06-14

### Wip

- Try to fix splinter tests

## [2023.06.12.3] - 2023-06-12

### Refactor

- Update flask API

## [2023.06.12.2] - 2023-06-12

### Bug Fixes

- Temp workaround for Heroku failure.

## [2023.06.05.3] - 2023-06-05

### Bug Fixes

- Forgot to compile assets once again.

## [2023.06.05.2] - 2023-06-05

### Features

- Export ontologies.

## [2023.06.05.1] - 2023-06-05

### Bug Fixes

- Remove log when call from CLI + add "components" CLI command.

## [2023.05.26.2] - 2023-05-26

### Bug Fixes

- Forgot assets (once more).

## [2023.05.26.1] - 2023-05-26

### Features

- Work on contents backoffice.
- Content management.

## [2023.05.25.3] - 2023-05-25

### Refactor

- Datatables.
- Datatables.

## [2023.05.25.2] - 2023-05-25

### Features

- Use datatable component for contents view.

## [2023.05.25.1] - 2023-05-25

### Features

- WIP dashboard.

## [2023.05.24.1] - 2023-05-24

### Miscellaneous Tasks

- Correct debian dependencies.

## [2023.05.17.4] - 2023-05-17

### Bug Fixes

- CSP config

## [2023.05.17.1] - 2023-05-17

### Features

- Add tracking by shynet.

## [2023.05.15.5] - 2023-05-15

### Bug Fixes

- We still must build the assets.

## [2023.05.15.4] - 2023-05-15

### Features

- Better dashboard integration (can be easily secured).

## [2023.05.15.3] - 2023-05-15

### Bug Fixes

- Change initialisation order.

## [2023.05.15.2] - 2023-05-15

### Chore

- Update deps

### Features

- Mount Dramtiq dashboard on /drama/

## [2023.05.15.1] - 2023-05-15

### Bug Fixes

- Redis config on heroku.

## [2023.05.12.3] - 2023-05-12

### Bug Fixes

- Loguru error on prod.

## [2023.05.12.2] - 2023-05-12

### Bug Fixes

- Remove old rq-based tasks.

## [2023.05.12.1] - 2023-05-12

### Features

- Start work on transactional emails.
- Finish Dramatiq integration.

### Refactor

- Try to use Dramatiq instead of RQ.
- Components / services registration via dedicated signal.

## [2023.05.11.3] - 2023-05-11

### Bug Fixes

- Mail = back to Gandi.

## [2023.05.11.1] - 2023-05-11

### Bug Fixes

- Fix some warnings.
- Fix registration and replace flask-mailing by flask-mailman.

## [2023.05.05.1] - 2023-05-05

### Revert

- Use a working email address.

## [2023.05.04.4] - 2023-05-04

### Config

- Tweak settings.

## [2023.05.04.2] - 2023-05-04

### Bug Fixes

- Prebuild vite assets because fuck heroku
- Tweak text.

## [2023.05.04.1] - 2023-05-04

### Bug Fixes

- Typing issues on search.

## [2023.05.02.1] - 2023-05-02

### Features

- Only show "european" languages.
- KYC et WIP.

## [2023.04.27.3] - 2023-04-27

### Features

- Forms.

## [2023.04.27.2] - 2023-04-27

### Bug Fixes

- Adt bump-version no longer has `--rule` option.

## [2023.04.21.1] - 2023-04-21

### Features

- Menu component (WIP).
- KYC wizard.

## [2023.04.19.3] - 2023-04-19

### Features

- Renaming.

## [2023.04.19.2] - 2023-04-19

### Bug Fixes

- Workaround redis issue.

### Features

- Wire des communiqués sur le business wall.

### Refactor

- Components framework (WIP).
- Move common components to a "common" module.

## [2023.04.14.1] - 2023-04-14

### Bug Fixes

- Workaround weasyprint installation issue is some cases.

### Features

- Tweak business wall.
- Start work on KYC.
- Start of KYC.

### Devops

- Nua config.
- Deploy using Nua (WIP).

## [2023.04.07.2] - 2023-04-07

### Features

- Business wall.

## [2023.04.07.1] - 2023-04-07

### Bug Fixes

- Route was not declared.

### Features

- Remove info (as requested by customer).
- "fake news" generator.
- Screenshoting (not working yet)
- Tweak design of business wall.

### Testing

- Make playright test parametrizable by base-url.
- Work on e2e tests.

### Devops

- Try to build with Nua (not working).

## [2023.03.31.3] - 2023-03-31

### Features

- Business wall.

## [2023.03.31.2] - 2023-03-31

### Testing

- E2e tests.

## [2023.03.31.1] - 2023-03-31

### Testing

- Introduce Playwright e2e tests.

## [2023.03.30.1] - 2023-03-30

### AI

- Experimenting with Gensim.

### Feat

- Business wall.

### Features

- Get version.
- Start work on blob storage and web content.

### Refactor

- Cleanup org model and add new field.

### Testing

- Test against Postgres, not SQLite.

## [2023.03.24.1] - 2023-03-24

### Features

- Start work on stats.
- Compute stats.
- Stats (UI)
- Tweak stats module.

## [2023.03.23.1] - 2023-03-23

### Bug Fixes

- Tweak CSS.

### Features

- Tweak invoice model.
- "performance" -> "performance réputationnelle".
- Admin/contents.
- Admin/transactions.
- Generate transaction and display them better.

### Refactor

- Html generation (not ready yet).
- Refact backoffice, add transactions.
- Admin module.

## [2023.03.21.1] - 2023-03-21

### Features

- Start work on mailer.

### Refactor

- Replace ad-hoc scanner with Venusian.
- Move "register_macros" to main
- Use lookups instead of ad-hoc registration.
- Introduce common lib for IOC.

### Testing

- Fix noxfile.

## [2023.03.16.4] - 2023-03-16

### Bug Fixes

- Use more compressed archive of nodejs

## [2023.03.16.2] - 2023-03-16

### Bug Fixes

- Missing dependency on weasyprint

## [2023.03.16.1] - 2023-03-16

### Features

- Start work on invoices.
- Billing UI.
- Generate PDF invoices.

### Refactor

- Cleanup / split WIP module.

### Testing

- Properly test invoices (WIP).

## [2023.03.15.2] - 2023-03-15

### Features

- Add publisher to posts.
- Add publisher.

## [2023.03.12.1] - 2023-03-12

### Bug Fixes

- Deps + try do deal with email error.

## [2023.03.11.1] - 2023-03-11

### Bug Fixes

- Reputation

## [2023.03.10.9] - 2023-03-10

### Bug Fixes

- Forgot to commit migration

## [2023.03.10.7] - 2023-03-10

### Bug Fixes

- Whoa, mypy found an actual, hard to find, bug.

### Refactor

- Use/improve "class Meta".

## [2023.03.10.6] - 2023-03-10

### Features

- Randomize reputation (a bit)

## [2023.03.10.4] - 2023-03-10

### Bug Fixes

- Prod requirements.

## [2023.03.10.1] - 2023-03-10

### Features

- Publication status + transaction dashboard

## [2023.03.09.7] - 2023-03-09

### Features

- Start work on wallets and transactions.

### Refactor

- Isolate faker.

## [2023.03.09.6] - 2023-03-09

### Refactor

- Cleanup.

## [2023.03.09.3] - 2023-03-09

### Features

- Send emails (using flask-mailing).

## [2023.03.09.2] - 2023-03-09

### Bug Fixes

- Wakaq extension.

### Features

- Working on queues.
- Show real reputation.

## [2023.03.09.1] - 2023-03-09

### Features

- RQ integration.

## [2023.03.08.9] - 2023-03-08

### Refactor

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

### Bug Fixes

- Wallet model.
- Remove duplicate column
- Bug with components  labels.

### Features

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

### Refactor

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
- Cleanup post SQLA 2.0.
- Cleanup data model.
- Cleanup.
- Use generated "snowflake ids".
- Encode ids.

### Testing

- Fix deptry config.
- Add architecture tests

### Deps

- Replace flask-babelex by flask-babel.

## [2023.02.17.2] - 2023-02-17

### Features

- Reput

## [2023.02.17.1] - 2023-02-17

### Features

- Late-night work on superadmin (WIP)

## [2023.02.16.2] - 2023-02-16

### Features

- Add rule engine for admin UI.

## [2023.02.15.1] - 2023-02-15

### Features

- Prototype "superadmin" app.
- Proto admin

### Refactor

- Use SQLA2 API.
- More SQLA2 cosmits.

## [2023.02.13.2] - 2023-02-13

### Refactor

- Vendorize livewire.

## [2023.02.13.1] - 2023-02-13

### Refactor

- Refact / cleanup front-end code.
- Cleanup livewire & alpine-components.

### WIP

- New / alternative admin.

### Wording

- Reputation -> performance.

## [2023.02.10.1] - 2023-02-10

### Features

- Karma + admin

## [2023.02.09.1] - 2023-02-09

### Bug Fixes

- Icons issues + tweak footer.

## [2023.02.03.3] - 2023-02-03

### Features

- Mockup com'room.

## [2023.02.03.1] - 2023-02-02

### Features

- Implémentation des specs des Com'Room (WIP).

### Refactor

- Rename classes, cleanup a bit.
- Move template to a generic directory.

## [2023.02.02.1] - 2023-02-02

### WIP

- Working on tables.

## [2023.01.26.3] - 2023-01-26

### Wording

- Formations -> webinars.

## [2023.01.20.1] - 2023-01-20

### Features

- Work on reputation / performance.
- Newsroom (wip).
- Newsroom (wip)

### Refactor

- Use better JSON type.
- Import table as t.

## [2023.01.17.5] - 2023-01-17

### Bug Fixes

- Lint warnings.

### Features

- Proto newsroom.
- Tweak WIP menu.

### Miscellaneous Tasks

- Fix tox issues.
- Make lint

### Refactor

- Convert doit script to invoke.

### Devops

- Nua config.

## [2023.01.06.1] - 2023-01-06

### Bug Fixes

- Css fix for search page.

### Documentation

- Update README

### Features

- Add rq.
- Work on search.
- Search.
- Delegation (WIP).

### Cloud

- Still tweaking heroku deployment.

## [2022.12.22.1] - 2022-12-22

### Bug Fixes

- Missing deps.
- Add missing markdown dependency.
- Try workaround to get npm.

### Features

- Generate static files on startup.
- Marketing content.

### Devops

- Heroku runtime.

## [2022.12.21.1] - 2022-12-21

### Bug Fixes

- Add missing temp logo.

### Features

- Start using Typesense.
- Use typesense.
- Add footer + use loguru for proper logs.
- Public pages.

## [2022.11.28.3] - 2022-11-28

### Bug Fixes

- Workaround filter bugs.
