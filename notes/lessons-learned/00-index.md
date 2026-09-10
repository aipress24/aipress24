# Lessons Learned — AIpress24

Transferable rules distilled from real incidents. Each entry is a **Rule** in bold — checkable against code — followed by the evidence that earned it. Read this before an audit, a review, or a cross-cutting change.

Organised by theme, not chronology. The point is to not hit the same class of bug again.

One file per theme, alongside this one. This page is the index; add a rule to the theme it belongs to, and a new theme here.

| Theme | Rules | |
|---|---|---|
| [Working Method](01-working-method.md) | 13 | how to approach a bug, an audit, a refactor |
| [Architecture & Contracts](02-architecture-and-contracts.md) | 10 | module design, data ownership, return types |
| [Databases, ORM & Migrations](03-databases-orm-and-migrations.md) | 10 | SQLAlchemy, portability, schema change |
| [Templates & Rendering](04-templates-and-rendering.md) | 6 | Jinja, autoescape, components |
| [Security & Trust Boundaries](05-security-and-trust-boundaries.md) | 5 |  |
| [Testing](06-testing.md) | 14 | no mocks, test layers, what to assert |
| [HTTP & Browser](07-http-and-browser.md) | 2 |  |
| [Email & Notifications](08-email-and-notifications.md) | 4 |  |
| [Stripe](09-stripe.md) | 1 |  |
| [Type Checker Hygiene](10-type-checker-hygiene.md) | 4 |  |
| [E2E (Playwright)](11-e2e-playwright.md) | 2 |  |
| [Checklists](12-checklists.md) | 5 |  |

---

## Every rule, in one list

**[Working Method](01-working-method.md)**

- [Reproduce the exact symptom before touching code](01-working-method.md#reproduce-the-exact-symptom-before-touching-code)
- [An audit's severity labels are unreliable in both directions](01-working-method.md#an-audits-severity-labels-are-unreliable-in-both-directions)
- [The fix must not be worse than the bug](01-working-method.md#the-fix-must-not-be-worse-than-the-bug)
- [Cross-cutting and security fixes carry a follow-up regression budget](01-working-method.md#cross-cutting-and-security-fixes-carry-a-follow-up-regression-budget)
- [Product decisions get reversed after the first demo](01-working-method.md#product-decisions-get-reversed-after-the-first-demo)
- [Two-phase refactor: disable, then clean](01-working-method.md#two-phase-refactor-disable-then-clean)
- [Extract a utility on the third use, not the first](01-working-method.md#extract-a-utility-on-the-third-use-not-the-first)
- [Rename beats a boolean parameter for behaviour switches](01-working-method.md#rename-beats-a-boolean-parameter-for-behaviour-switches)
- [Trace the full chain before adding a step](01-working-method.md#trace-the-full-chain-before-adding-a-step)
- [Short spec before each MVP](01-working-method.md#short-spec-before-each-mvp)
- [Synthesis spec beats N parallel sources](01-working-method.md#synthesis-spec-beats-n-parallel-sources)
- [A working-tree scan is not a repository scan](01-working-method.md#a-working-tree-scan-is-not-a-repository-scan)
- [A probe that reports nothing must first be shown to report something](01-working-method.md#a-probe-that-reports-nothing-must-first-be-shown-to-report-something)

**[Architecture & Contracts](02-architecture-and-contracts.md)**

- [Registry pattern over monkey-patching](02-architecture-and-contracts.md#registry-pattern-over-monkey-patching)
- [Composition over inheritance for metadata](02-architecture-and-contracts.md#composition-over-inheritance-for-metadata)
- [Denormalize only when write points are finite](02-architecture-and-contracts.md#denormalize-only-when-write-points-are-finite)
- [Projected data needs a single source of truth](02-architecture-and-contracts.md#projected-data-needs-a-single-source-of-truth)
- [Collapsing a structured outcome into `bool` swallows the actionable part](02-architecture-and-contracts.md#collapsing-a-structured-outcome-into-bool-swallows-the-actionable-part)
- [Know whether your accessor raises or returns None](02-architecture-and-contracts.md#know-whether-your-accessor-raises-or-returns-none)
- [Unify return types across subclasses](02-architecture-and-contracts.md#unify-return-types-across-subclasses)
- [Filtering across two datasets requires one canonical key space](02-architecture-and-contracts.md#filtering-across-two-datasets-requires-one-canonical-key-space)
- [Stripe Customer = Organisation, not person](02-architecture-and-contracts.md#stripe-customer-organisation-not-person)
- [A filter that falls back to "everything" must run last](02-architecture-and-contracts.md#a-filter-that-falls-back-to-everything-must-run-last)

**[Databases, ORM & Migrations](03-databases-orm-and-migrations.md)**

- [SQLite-green does not imply Postgres-green](03-databases-orm-and-migrations.md#sqlite-green-does-not-imply-postgres-green)
- [Portable SQL, or one construct that compiles per dialect](03-databases-orm-and-migrations.md#portable-sql-or-one-construct-that-compiles-per-dialect)
- [Hybrid property double API](03-databases-orm-and-migrations.md#hybrid-property-double-api)
- [`Mapped[dict]` vs `Mapped[list]` is not a typing cosmetic](03-databases-orm-and-migrations.md#mappeddict-vs-mappedlist-is-not-a-typing-cosmetic)
- [`ClassVar` goes on the outside](03-databases-orm-and-migrations.md#classvar-goes-on-the-outside)
- [Compare by ID, not by instance, in `.where()`](03-databases-orm-and-migrations.md#compare-by-id-not-by-instance-in-where)
- [Keyset pagination must be PK-type-agnostic](03-databases-orm-and-migrations.md#keyset-pagination-must-be-pk-type-agnostic)
- [Empty-list filter trap](03-databases-orm-and-migrations.md#empty-list-filter-trap)
- [Production commits at the view layer](03-databases-orm-and-migrations.md#production-commits-at-the-view-layer)
- [Defaults apply at insert, not at construction](03-databases-orm-and-migrations.md#defaults-apply-at-insert-not-at-construction)

**[Templates & Rendering](04-templates-and-rendering.md)**

- [A global rendering-policy change has a blast radius across every template](04-templates-and-rendering.md#a-global-rendering-policy-change-has-a-blast-radius-across-every-template)
- [`tojson` is not safe in a double-quoted HTML attribute](04-templates-and-rendering.md#tojson-is-not-safe-in-a-double-quoted-html-attribute)
- [Under `StrictUndefined`, every attribute chain is a latent 500](04-templates-and-rendering.md#under-strictundefined-every-attribute-chain-is-a-latent-500)
- [Sibling components share an implicit interface contract](04-templates-and-rendering.md#sibling-components-share-an-implicit-interface-contract)
- [The rendering *path* is part of a reused component's contract](04-templates-and-rendering.md#the-rendering-path-is-part-of-a-reused-components-contract)
- [A server-driven re-render must preserve in-flight user state](04-templates-and-rendering.md#a-server-driven-re-render-must-preserve-in-flight-user-state)

**[Security & Trust Boundaries](05-security-and-trust-boundaries.md)**

- [Client-side sanitisation is not a security boundary](05-security-and-trust-boundaries.md#client-side-sanitisation-is-not-a-security-boundary)
- [Session-id idempotency guards must verify ownership](05-security-and-trust-boundaries.md#session-id-idempotency-guards-must-verify-ownership)
- [Flask-Security only purges auth keys at login](05-security-and-trust-boundaries.md#flask-security-only-purges-auth-keys-at-login)
- [A record fetched by id must obey the rule its list obeys](05-security-and-trust-boundaries.md#a-record-fetched-by-id-must-obey-the-rule-its-list-obeys)
- [An uploaded filename decides the Content-Type it is served as](05-security-and-trust-boundaries.md#an-uploaded-filename-decides-the-content-type-it-is-served-as)

**[Testing](06-testing.md)**

- [No mocks — test real behaviour, not mock interactions](06-testing.md#no-mocks-test-real-behaviour-not-mock-interactions)
- [Match the test layer to the failure layer](06-testing.md#match-the-test-layer-to-the-failure-layer)
- ["Status 200" is not "rendered correctly"](06-testing.md#status-200-is-not-rendered-correctly)
- [`b_integration` vs `c_e2e`](06-testing.md#b_integration-vs-c_e2e)
- [Intentional-but-surprising behaviour needs a self-documenting test](06-testing.md#intentional-but-surprising-behaviour-needs-a-self-documenting-test)
- [Assert the exact set, not the count](06-testing.md#assert-the-exact-set-not-the-count)
- [Fixtures must use the production data format](06-testing.md#fixtures-must-use-the-production-data-format)
- [Coverage ≠ quality; more tests ≠ better tests](06-testing.md#coverage-quality-more-tests-better-tests)
- [Test business logic, not trivial accessors](06-testing.md#test-business-logic-not-trivial-accessors)
- [Avoid inheritance and mixins in tests — but do use parametrization](06-testing.md#avoid-inheritance-and-mixins-in-tests-but-do-use-parametrization)
- [One test file per pattern, not per instance](06-testing.md#one-test-file-per-pattern-not-per-instance)
- [Pin the date](06-testing.md#pin-the-date)
- [Anti-spam bypasses are mandatory in mail test harnesses](06-testing.md#anti-spam-bypasses-are-mandatory-in-mail-test-harnesses)
- [Don't test framework behaviour, or private internals](06-testing.md#dont-test-framework-behaviour-or-private-internals)

**[HTTP & Browser](07-http-and-browser.md)**

- [Idempotent GET on confirmation pages](07-http-and-browser.md#idempotent-get-on-confirmation-pages)
- [Werkzeug 3+ caps forms at 500 KB](07-http-and-browser.md#werkzeug-3-caps-forms-at-500-kb)

**[Email & Notifications](08-email-and-notifications.md)**

- [Send before mutating the state the email cites](08-email-and-notifications.md#send-before-mutating-the-state-the-email-cites)
- [Couple recipient creation to the notification trigger](08-email-and-notifications.md#couple-recipient-creation-to-the-notification-trigger)
- [Name mail variables by type, not by role](08-email-and-notifications.md#name-mail-variables-by-type-not-by-role)
- [Verify "familiar" imports before writing send-mail code](08-email-and-notifications.md#verify-familiar-imports-before-writing-send-mail-code)

**[Stripe](09-stripe.md)**

- [Never hit the Stripe API at render time for a displayed price](09-stripe.md#never-hit-the-stripe-api-at-render-time-for-a-displayed-price)

**[Type Checker Hygiene](10-type-checker-hygiene.md)**

- [`case Path(template_path):` is a fake pattern match](10-type-checker-hygiene.md#case-pathtemplate_path-is-a-fake-pattern-match)
- [Prefer stdlib `enum.StrEnum` over `aenum.StrEnum`](10-type-checker-hygiene.md#prefer-stdlib-enumstrenum-over-aenumstrenum)
- [`type: ignore` outlives the tool that justified it](10-type-checker-hygiene.md#type-ignore-outlives-the-tool-that-justified-it)
- [Prefer an annotated local binding to a suppression](10-type-checker-hygiene.md#prefer-an-annotated-local-binding-to-a-suppression)

**[E2E (Playwright)](11-e2e-playwright.md)**

- [`page.request.post()` does not carry `BrowserContext` cookies](11-e2e-playwright.md#pagerequestpost-does-not-carry-browsercontext-cookies)
- [Vite HMR sockets block Firefox e2e beyond ~20 tests](11-e2e-playwright.md#vite-hmr-sockets-block-firefox-e2e-beyond-20-tests)

**[Checklists](12-checklists.md)**

- [Before merging tests](12-checklists.md#before-merging-tests)
- [Before merging a cross-cutting or schema change](12-checklists.md#before-merging-a-cross-cutting-or-schema-change)
- [Before writing a template](12-checklists.md#before-writing-a-template)
- [Before declaring a change verified](12-checklists.md#before-declaring-a-change-verified)
- [Before acting on a bug or a finding](12-checklists.md#before-acting-on-a-bug-or-a-finding)
