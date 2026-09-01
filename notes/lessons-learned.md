# Lessons Learned — AIpress24

Transferable rules distilled from real incidents. Each entry is a **Rule** in bold — checkable against code — followed by the evidence that earned it. Read this before an audit, a review, or a cross-cutting change.

Organised by theme, not chronology. The point is to not hit the same class of bug again.

## Table of Contents

1. [Working Method](#working-method) — how to approach a bug, an audit, a refactor
2. [Architecture & Contracts](#architecture--contracts) — module design, data ownership, return types
3. [Databases, ORM & Migrations](#databases-orm--migrations) — SQLAlchemy, portability, schema change
4. [Templates & Rendering](#templates--rendering) — Jinja, autoescape, components
5. [Security & Trust Boundaries](#security--trust-boundaries)
6. [Testing](#testing) — no mocks, test layers, what to assert
7. [HTTP & Browser](#http--browser)
8. [Email & Notifications](#email--notifications)
9. [Stripe](#stripe)
10. [Type Checker Hygiene](#type-checker-hygiene)
11. [E2E (Playwright)](#e2e-playwright)
12. [Checklists](#checklists)

---

## Working Method

### Reproduce the exact symptom before touching code

**Rule**: a red test emitting the *same* error string as production is the difference between a one-commit fix and a multi-commit thrash.

Every fix that started from an exact reproduction landed in one pass. Every fix that guessed thrashed: a CSS column bug took 4 attempts because the first 3 treated the CSS symptom instead of the unescaped-HTML cause. When you can't reproduce at the unit layer, go *up* a layer (real Jinja env, real browser) rather than guessing.

### An audit's severity labels are unreliable in both directions

**Rule**: an audit — human or agent — produces *leads*, not *severities*. Verify each finding independently before acting on it, or dismissing it.

A fan-out audit **over-graded** ("critical stored XSS" on a premise that was false; "HIGH silent data loss" on idempotent revokes) and **under-graded** ("medium cosmetic" was every admin table rendering as escaped literal text in production; "latent low" was a `KeyError` 500ing the public members directory). Acting on the labels in either direction would have wasted effort *and* shipped breakage.

Be especially wary of "dead code" findings: confirm by execution (set intersections, call-site reachability, a failing characterization test), never by inspection, before deleting.

### The fix must not be worse than the bug

**Rule**: a fix that makes the symptom invisible is a worse bug — now undiagnosable. Never write a test that asserts the broken behaviour.

A blank-page "fix" hid the empty response instead of redirecting to an actionable surface, and a test asserted `response.data == b""`, codifying it. If the only test you can write asserts the symptom, you haven't found the root cause yet.

### Cross-cutting and security fixes carry a follow-up regression budget

**Rule**: a cross-cutting fix is not "done" at merge — budget for a wave of regressions in code paths that quietly depended on the old, lax behaviour.

One correct autoescape fix spawned three downstream bugs over a session. Land such changes early in a cycle, add sentinels at the policy boundary, and watch the error tracker for a week before calling it closed.

### Product decisions get reversed after the first demo

**Rule**: phase delivery so each decision is an independently revertible commit.

Capturing a decision up front does not freeze it — seeing the running result changes minds. Because one feature shipped in 3 independent phases, a reversal touched one filter instead of a monolith.

### Two-phase refactor: disable, then clean

**Rule**: introduce the new model and disable dependent tests in phase one; drop the old model and re-enable tests in phase two.

Better than an atomic swap. Write an explicit "tests disabled, re-enable after X is removed" marker so the debt doesn't sleep — and **schedule the re-enable as a dedicated goal**, not a vague follow-up, or the "temporary" disable becomes permanent and suite confidence silently erodes.

### Extract a utility on the third use, not the first

**Rule**: two usages → copy. Third usage → factor.

Premature abstraction (at the second usage) doesn't survive real-world variance.

### Rename beats a boolean parameter for behaviour switches

**Rule**: encode the intent in the name — don't add `active: bool = True`.

`get_business_wall_for_organisation()` → `get_active_business_wall_for_organisation()` revealed call sites that implicitly assumed "active" without checking, plus a few that wanted *any* BW. Explicit renaming forces callers to articulate which variant they need.

### Trace the full chain before adding a step

**Rule**: read workflow → makefile → tool chain before adding a "missing" check.

`ty check` was nearly added to two CI workflows that both already invoke `make lint`, which already runs it.

### Short spec before each MVP

**Rule**: 1-2 pages before any code — an anchor, not a contract.

Five MVPs landed in one week without scope creep, each preceded by a short spec. It forces a "V0 vs vision" arbitration and remains a reusable artifact for client calls.

### Synthesis spec beats N parallel sources

**Rule**: when several analyses cover one topic, write a synthesis that primes over them — don't reconcile them pairwise.

Four parallel analyses drifted into subtle divergences (inconsistent naming, three different price tables, 3 vs 9 webhook counts). Banner each superseded doc with "Updated <date>, see <new>" — otherwise readers keep treating the old one as authoritative.

---

## Architecture & Contracts

### Registry pattern over monkey-patching

**Rule**: never monkey-patch framework objects with custom attributes — use a typed registry.

```python
# BAD — needs `# type: ignore[attr-defined]`, no autocomplete, no validation
blueprint.nav = {"label": "Marketplace", "icon": "shopping-cart", "order": 40}

# GOOD
configure_nav(blueprint, label="Marketplace", icon="shopping-cart", order=40)
```

The registry keeps a `TypedDict` config in a module-level dict keyed by blueprint name.

### Composition over inheritance for metadata

**Rule**: prefer a registry when you can't modify the base class, when the metadata is optional, or when the object's type must stay unchanged.

Inheritance (`class NavBlueprint(Blueprint)`) is type-safe but couples to the base class and can't be retrofitted.

### Denormalize only when write points are finite

**Rule**: a projected column is only safe if you can name every write site and cover it.

`Organisation.bw_id` / `bw_active` are safe because they're written at exactly the BW activation/deactivation points. Conversely, the events mirror can carry denormalized geo columns because `event_receiver` is its single write path — the KYC profile and marketplace offers cannot, since their forms write from several places.

### Projected data needs a single source of truth

**Rule**: anything derivable from something else gets one representation and one access point.

`Organisation.logo` and `BusinessWall.logo` could diverge. Pick one canonical home, wrap reads in a utility.

### Collapsing a structured outcome into `bool` swallows the actionable part

**Rule**: when a function can fail for several distinct, user-correctable reasons, return an enum or dataclass — never `bool`.

`invite_user_role` returned `True/False`; the route discarded the reason. A user typed an email outside the org, saw the modal close, assumed success — the invitation was silently dropped. **"Silent success" is the worst failure mode: nobody files a bug, they just lose data.**

### Know whether your accessor raises or returns None

**Rule**: the raises-vs-returns-`None` contract is part of the signature. Confirm it at the call site; don't infer it from the name.

`repo.get(id)` raises `NotFoundError`; `repo.get_one_or_none(id=…)` returns `None`. Code assuming the second while calling the first turned a normal "not found" into an unhandled 500.

### Unify return types across subclasses

**Rule**: a Liskov violation compiles fine and breaks at the call site.

`get_authors()` returned `list[User]` in one subclass, `None` in another, `Query` in a third. Unify to `Iterable[User] | None` to force callers to handle absence.

### Filtering across two datasets requires one canonical key space

**Rule**: prove both sides use the same key *before* trusting a join, filter, or count.

A "0 everywhere" or "nothing filtered" symptom is almost always a key-space mismatch — qualified `"Parent / Child"` vs bare, code vs label, trimmed vs raw — not a logic bug.

### Stripe Customer = Organisation, not person

**Rule**: bind `stripe_customer_id` to the Organisation — the legal payer — not to a User or a Subscription row.

Subscriptions come and go; the Customer persists across them, and the current BW Manager accesses the portal regardless of who originally subscribed.

---

## Databases, ORM & Migrations

### SQLite-green does not imply Postgres-green

**Rule**: any change touching schema, migrations, raw SQL, or type-sensitive operators (`>`, casts, JSON ops) must run `make test-postgres` before it counts as tested.

SQLite is permissive about types and tolerant of drift; Postgres is strict. An `EventPost.publisher_id` fix passed the whole SQLite suite, then crashed production with `UndefinedColumn`.

**The converse bites just as hard.** Hybrid-property expressions using `split_part` (Postgres-only) made the geographic filters of four modules return nothing on SQLite for months — hidden behind `except OperationalError: return []`, so they read as *empty* rather than *broken*. A green suite on either backend alone is close to no signal for anything dialect-sensitive.

### Portable SQL, or one construct that compiles per dialect

**Rule**: don't write dialect-specific SQL in a model. If a primitive genuinely differs, isolate it in one `@compiles` construct and share it.

`substr`, `||`, `coalesce`, `case` are common ground. Position search is not (`strpos` vs `instr`), nor is `->>` with an integer index — use SQLAlchemy's `col[key].as_string()`, which compiles for both. `app/lib/geoloc.py` is the worked example: one Python parser, one SQL builder, and a test asserting they agree on the same inputs.

### Hybrid property double API

**Rule**: a computed property that must be filterable needs `@hybrid_property` *plus* `.expression` — and the expression must be portable.

A plain `@property` reads in Python but breaks ORM filters. Beware the trap that follows: the Python half and the SQL half are two implementations of one rule, and they drift. Assert they agree, or derive both from one shared helper.

### `Mapped[dict]` vs `Mapped[list]` is not a typing cosmetic

**Rule**: pick the correct collection type — `ty` cascades 15+ errors when wrong.

Both are JSON columns at the DB level, but `ty` rejects `.append` and indexed iteration on a `Mapped[dict]`.

### `ClassVar` goes on the outside

**Rule**: `ClassVar[Mapped[...]]`, never `Mapped[ClassVar[...]]`.

Inverted, SQLAlchemy tries to map the static value.

### Compare by ID, not by instance, in `.where()`

**Rule**: `.where(Model.owner_id == user.id)` — never `.where(Model.owner == user)`.

The instance form works by accident; the ID form is explicit, avoids a relationship load, and doesn't break on detached instances.

### Keyset pagination must be PK-type-agnostic

**Rule**: never fabricate a "smaller than any value" sentinel — its type leaks.

A back-fill migration seeded `last_id = -(2**63)`, worked on 8 integer-PK tables, and exploded on a varchar PK: `operator does not exist: character varying > bigint`. Omit the `WHERE pk > …` clause on the first page (`last_id = None`), then switch to the bounded query.

### Empty-list filter trap

**Rule**: for optional SQL filters use `if authors:` — not `if authors is not None`.

`.where(Model.owner_id.in_([]))` matches nothing, silently. An empty list means "no filter", not "match nothing".

### Production commits at the view layer

**Rule**: routes commit; service helpers stay transaction-neutral.

The test harness wraps each test in a savepoint. A helper calling `db.session.commit()` leaks data past the rollback — caught late, by a table-emptiness check at teardown.

### Defaults apply at insert, not at construction

**Rule**: `mapped_column(default=…)` leaves the attribute `None` until the first flush. Seed it in an `init` listener if any code reads it before.

Validation that runs in the same transaction as creation — an API that builds and publishes without an intermediate flush — sees `None` where the annotation promises a value.

---

## Templates & Rendering

### A global rendering-policy change has a blast radius across every template

**Rule**: when changing a cross-cutting rendering or serialization policy, enumerate every consumer class — macros, components, `from_string` call sites, `{% include %}`d partials. The ones that *bypass* the policy will hide the regression elsewhere.

Enabling Jinja autoescape was correct, and silently broke two unrelated things weeks apart: `@macro` helpers returning plain `str` rendered as literal `<div…>` text, and an inline JSON payload became unparseable so a JS widget never initialised. One widget *appeared* immune only because it renders via `from_string()` (no filename → autoescape off) — that bypass sent us looking in the wrong place. A policy change needs a sentinel test at the policy boundary, not at one call site.

### `tojson` is not safe in a double-quoted HTML attribute

**Rule**: single-quote the attribute (`data-x='{{ v|tojson }}'`) or use `<script type="application/json">`. Never double-quote.

Flask's `tojson` escapes `<`, `>`, `&` and `'`, but leaves `"` literal — it is JSON's own delimiter, so the first one closes the attribute. Three commits were burned rediscovering this.

### Under `StrictUndefined`, every attribute chain is a latent 500

**Rule**: any `a.b.c` where an intermediate can legitimately be `None` — optional FK, unfilled profile, draft state — is a production crash waiting for the first such row.

`{{ user.organisation.name }}` 500'd a whole page for any participant with no organisation. Guard with `{% if a.b %}` or expose a view-model property that null-coalesces.

### Sibling components share an implicit interface contract

**Rule**: when several components are invoked through the same call-site convention, that convention *is* a contract. Adding a kwarg to one means every interchangeable sibling must accept it.

`component("post-card", …, class_=…)` and `component("event-card", …, class_=…)` were called identically; only one accepted `class_` → `TypeError`, 500. Consider a shared base or a `**extra` sink for presentational kwargs.

### The rendering *path* is part of a reused component's contract

**Rule**: prefer the pattern already proven *on the target page* over one proven *elsewhere*.

Reusing a working widget through a different rendering path (`{% include %}` under autoescape vs `from_string` without) re-introduced a class of bug the original had already solved.

### A server-driven re-render must preserve in-flight user state

**Rule**: whenever the server re-renders a form from fresh state (HTMX swap, wizard step, live filter), explicitly preserve what the user has already picked.

A cascade's "≥ 1 match" filter would have stripped an option the user had *already selected* once the narrowed pool no longer matched it — silently deleting their own choice mid-edit. "The server is the source of truth" is false for the input currently being edited.

---

## Security & Trust Boundaries

### Client-side sanitisation is not a security boundary

**Rule**: sanitise on write *and* escape on render. One layer is a single point of failure.

A rich-text editor renders HTML in the browser, but an attacker POSTs raw HTML directly — the editor is never in that path. Treating its output as trusted-and-`|safe` was a stored-XSS vector. The fix was defence in depth: autoescape on render, a `|sanitize` filter, and a `SanitizedHTML` `TypeDecorator` scrubbing on write, plus a back-fill migration.

### Session-id idempotency guards must verify ownership

**Rule**: an object id stored in the session is not proof of ownership — re-validate before short-circuiting.

An orphan BW referenced by a stale `session["bw_id"]` produced a success page followed by an unauthorized dashboard.

### Flask-Security only purges auth keys at login

**Rule**: add a `user_authenticated` handler that scrubs application-prefix session keys.

Filter state under `events:*`, `wire:*`, `swork:*`, `biz:*` persists across user switches in the same browser; Flask-Security cleans only Flask-Login keys.

---

## Testing

### No mocks — test real behaviour, not mock interactions

**Rule**: every mock has a non-mock alternative. Find it before reaching for `MagicMock`.

Mocks drift from the implementation, pass when real code would fail, and test interactions instead of state.

| Situation | Instead of a mock | Use |
|---|---|---|
| External service (DB, API) | mock the client | in-memory DB, test server |
| Feature flag / guard | mock the flag | test the logic directly |
| Time-dependent code | mock `datetime` | pass time as a parameter |
| Random behaviour | mock `random` | seed the RNG, or inject the generator |
| File system | mock file ops | `tmp_path` fixture |

A `MagicMock` answers truthy to everything, so a guard reading `item.publisher.review_required` silently takes the wrong branch. Prefer an explicit stub object.

### Match the test layer to the failure layer

**Rule**: a browser-init bug needs a Playwright sentinel; a template bug needs a real-env render; a "passing" endpoint test that tolerates a redirect is not testing the page.

Three false-confidence traps in one session: server-side unit tests proved cascade *data* was filtered correctly but couldn't see that the widget never *initialised*; an e2e test tolerating `302` never rendered the partial, so a crash sailed to production on a URL with a green test; and mixing `c_e2e` with `b_integration` in one pytest run drops tables, producing errors that read like regressions.

### "Status 200" is not "rendered correctly"

**Rule**: for any page whose value *is* its rendered output, assert a concrete markup invariant — not just the status code.

Every admin table page asserted `status_code == 200`. After the autoescape change, `Table.render()` was escaped to literal `&lt;div…&gt;` — the admin became unreadable text — and every test stayed green for the whole period.

### `b_integration` vs `c_e2e`

**Rule**: any test that hits an HTTP route belongs in `c_e2e/`, even if it covers only an internal detail.

Direct function calls = integration; FlaskClient HTTP = e2e. Otherwise the same surface is tested on both sides and regressions become ambiguous to locate.

### Intentional-but-surprising behaviour needs a self-documenting test

**Rule**: behaviour a reasonable engineer would "fix" by mistake must carry a test that fails loudly, with a docstring stating the design intent.

The test is the durable comment; a code comment alone gets refactored away.

### Assert the exact set, not the count

**Rule**: counts hide semantics.

A legacy `assert len(user.roles) == 2` pinned a defective state — a role was added without removing the previous one — into a regression test.

### Fixtures must use the production data format

**Rule**: a fixture that fabricates a shape production never produces validates nothing.

Two fixtures built locations as `"FR CP 75000 Paris"` and `"75001 Paris"`; production always writes `"FRA / 75001 Paris"`. Positional parsing accepted the fakes by coincidence — the separator happened to fall in the same slot — so the tests certified a format that does not exist, and a real defect survived for months.

### Coverage ≠ quality; more tests ≠ better tests

**Rule**: before writing a test, ask what *new code path* it exercises.

37 tests were once added with coverage unchanged at 60%; a later cleanup removed 56 tests with coverage still unchanged. The redundant ones duplicated existing coverage, tested the same behaviour several ways, or verified third-party behaviour (`pytz`, `strftime`).

### Test business logic, not trivial accessors

**Rule**: one test per business rule, not one per attribute. Loop over an enum instead of writing one test per value.

Looping also catches new enum values without touching the test.

### Avoid inheritance and mixins in tests — but do use parametrization

**Rule**: tests must be readable in isolation. Duplication beats hidden indirection; `@pytest.mark.parametrize` is not the same pattern as a mixin.

A mixin obscures what's tested, spans stack traces across files, and couples unrelated modules. Parametrization keeps every case visible in one place. A small private helper per test class is fine.

### One test file per pattern, not per instance

**Rule**: if four files test near-identical functions, keep one that tests the *pattern* — and consider whether the functions should share code.

### Pin the date

**Rule**: never depend on `date.today()` in a test.

Several tests passed Monday-Thursday and broke on Friday (ISO week, weekday-of-month). Use clock injection or `freezegun`.

### Anti-spam bypasses are mandatory in mail test harnesses

**Rule**: bypass or reset `is_email_sending_allowed`, `partition_by_cap`, `_recent_dups` / `_over_cap` in test mode.

Without short-circuits, looping tests succeed once and then silently capture zero mails.

### Don't test framework behaviour, or private internals

**Rule**: trust your dependencies; test the public API, not the class behind it.

Test that generated ids are unique, not that the internal counter increments. And use the source-of-truth constant in assertions rather than a hardcoded copy of its value.

---

## HTTP & Browser

### Idempotent GET on confirmation pages

**Rule**: any GET route that creates an object must guard on the **real state**, not a session flag.

`/BW/confirmation/free` created two BWs on one GET: Firefox prefetch re-fired the handler while `session["bw_activated"]` was still true. Check whether the entity exists in the DB.

### Werkzeug 3+ caps forms at 500 KB

**Rule**: set `MAX_FORM_MEMORY_SIZE` to ~3× your max image size when accepting base64 uploads.

A 1 MB image becomes a ~1.4 MB form field and is silently rejected with a 413.

---

## Email & Notifications

### Send before mutating the state the email cites

**Rule**: if an email quotes state, send it before any mutation that invalidates it.

`cancel_rdv` reset `contact.date_rdv = None`; the cancellation email body cites that date and early-returns when it's `None`, so the original cancel-then-email order silently dropped the notification.

### Couple recipient creation to the notification trigger

**Rule**: a user-input path that must produce a notification later should create or reference the recipient entity *in the form*, not downstream.

A free-text email input wasn't stored as a Contact, so no notification could ever be sent. Replaced with a `<select>` of colleagues, which guarantees the Contact exists when the trigger fires.

### Name mail variables by type, not by role

**Rule**: `sender_mail` / `sender_full_name`, never `sender_name`.

Ambiguity between "person name" and "technical identifier" is a reliable source of the "I put the email in the name field" bug.

### Verify "familiar" imports before writing send-mail code

**Rule**: grep for the actual library first.

This project uses `flask_mailman` via `EmailService`, not `flask_mail.Message`. The familiar import would have crashed on the first cron run.

---

## Stripe

### Never hit the Stripe API at render time for a displayed price

**Rule**: mirror prices locally, fed by `price.created/updated/deleted` webhooks.

Any cache window between Stripe's authoritative price and the displayed one is a risk that the user pays an amount other than the one shown. The Checkout page remains the final authority on what's charged.

See also [Stripe Customer = Organisation](#stripe-customer--organisation-not-person) and [production commits at the view layer](#production-commits-at-the-view-layer).

---

## Type Checker Hygiene

### `case Path(template_path):` is a fake pattern match

**Rule**: never trust a positional `case` pattern on a stdlib type without `__match_args__`.

`pathlib.Path` has none; the branch raises `TypeError` at runtime the first time it's hit. Correct form: `case Path() as template_path:`. Pyrefly catches this, mypy doesn't.

### Prefer stdlib `enum.StrEnum` over `aenum.StrEnum`

**Rule**: pyrefly flags `not-iterable` and `not-a-type` on `aenum` subclasses; stdlib behaves identically for `StrEnum + auto()`.

### `type: ignore` outlives the tool that justified it

**Rule**: always use `type: ignore[specific-code]`, and audit them whenever you change checkers.

Migrating mypy → ty dropped 23 ignores, most dating from SQLAlchemy patterns long since fixed. The same happened again when `ty` gained a `redundant-cast` diagnostic: two casts labelled "work around a mypy bug" had outlived the bug, each dragging an extra `type: ignore` with it.

### Prefer an annotated local binding to a suppression

**Rule**: when a checker misreads a framework descriptor, bind the value to an annotated local instead of silencing a whole error code.

`mode: EventMode = self.mode` states what is true and keeps the checker's coverage everywhere else. Pyrefly has no SQLAlchemy support, so instance access on a mapped column types as `InstrumentedAttribute[T]` — the binding is the honest fix.

---

## E2E (Playwright)

### `page.request.post()` does not carry `BrowserContext` cookies

**Rule**: go through JS `fetch` via `page.evaluate(...)`, and always assert the final URL.

Authenticated POSTs silently bounce to `/auth/login` with status 200 and a login-form body. Five tests were green false positives until a uniform `"/auth/login" not in resp["url"]` assertion was added.

### Vite HMR sockets block Firefox e2e beyond ~20 tests

**Rule**: `route.abort()` on `**://localhost:3000/**` in an autouse fixture when testing against a dev server.

Firefox serializes new scripts behind earlier HMR sockets; DCL stalls indefinitely. Pages still render, just without HMR — which tests don't use.

---

## Checklists

### Before merging tests

- [ ] Does each test exercise a *distinct* code path?
- [ ] Real behaviour, not mocks? Stubs where a double is unavoidable?
- [ ] Our code, not framework/library behaviour?
- [ ] Business rules, not trivial accessors? Exact sets, not counts?
- [ ] Self-contained and readable in isolation — no mixins hiding logic?
- [ ] Fixtures use the **production data format**?
- [ ] Date-sensitive logic pinned via clock injection?
- [ ] No `db.session.commit()` outside a route?
- [ ] Page whose value is its rendered output? Assert markup, not `200`.

### Before merging a cross-cutting or schema change

- [ ] Touched schema, migration, raw SQL, or a typed operator? Ran `make test-postgres`?
- [ ] Any dialect-specific SQL (`split_part`, `->>` with an int index, `strpos`/`instr`)? Isolated behind one portable construct?
- [ ] Denormalized a column? Can you name every write site?
- [ ] A rule written twice (Python + SQL)? Is there a test asserting the two halves agree?
- [ ] Changed a rendering or serialization policy? Enumerated macros, components, `from_string` sites, included partials — and added a boundary sentinel?
- [ ] Budgeted for a wave of follow-up regressions?

### Before writing a template

- [ ] Embedding JSON? Single-quoted attribute or `<script type="application/json">`. Never `data-x="{{ …|tojson }}"`.
- [ ] Attribute chain `a.b.c` where an intermediate can be `None`? Guard it.
- [ ] Adding a kwarg to a component used via a shared convention? Update every sibling.
- [ ] Server re-renders a form the user is editing? Preserve in-flight selections.

### Before acting on a bug or a finding

- [ ] Reproduced the exact production error string in a red test?
- [ ] Treated the audit's severity as unverified — reproduced it, or proved "dead code" dead by execution?
- [ ] Is the fix making the symptom invisible rather than removing the cause?
- [ ] Multiple user-correctable failure modes? Return a structured outcome, not `bool`.
- [ ] Calling a repository getter? Confirmed raises-vs-returns-`None`?
- [ ] Counting or filtering A against taxonomy B? Proved both use the same canonical key?

---

*Merged May 2026 + Aug 2026 sources, reorganised by theme Sept 2026.*
*Sources: test-quality sprint and navigation registry refactor (Jan 2026), Stripe integration and W4–W20 weekly notes (Feb–May 2026), debug session 2026-05-12 → 05-17 (autoescape, ciblage, prod 500s, migration failure, e2e flakes), events chantier and geolocation portability audit (Aug–Sept 2026).*
