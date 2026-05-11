# Lessons Learned — AIpress24

Reusable knowledge from AIpress24 development. Each lesson captures something **non-obvious** that bit us at least once — preserved here so it doesn't bite again. Most impactful sections first.

## Table of Contents

1. [Architectural Principles](#architectural-principles) — cross-cutting design rules
2. [No Mocks Policy](#no-mocks-policy) — foundational testing philosophy
3. [Refactoring Discipline](#refactoring-discipline) — how to land big changes safely
4. [Testing Strategy](#testing-strategy) — what to test, how to organize
5. [Common Pitfalls](#common-pitfalls) — specific patterns to avoid
6. [HTTP & Browser Gotchas](#http--browser-gotchas) — web-layer surprises
7. [Email & Notifications](#email--notifications) — recipient/state ordering rules
8. [Stripe Integration](#stripe-integration) — payments-specific patterns
9. [SQLAlchemy & ORM Patterns](#sqlalchemy--orm-patterns) — Mapped, hybrid, filters
10. [Type Checker Hygiene](#type-checker-hygiene) — ty / pyrefly / mypy gotchas
11. [E2E Testing (Playwright)](#e2e-testing-playwright) — browser-automation-specific
12. [Documentation & Specs](#documentation--specs) — spec-driven workflow
13. [Quick Reference: Test Review Checklist](#quick-reference-test-review-checklist)

Each lesson starts with a one-line **Rule** in bold, followed by the context, example, and / or rationale. Long-form lessons use a `**Problem**:` / `**Solution / Lesson**:` split.

---

## Architectural Principles

Cross-cutting rules that shape how we design modules, contracts, and data ownership. These are the lessons most likely to be re-applicable to any future change.

### Registry Pattern over Monkey-Patching

**Rule**: never monkey-patch framework objects with custom attributes — use a typed registry instead.

**Problem**: adding custom attributes to framework objects (monkey-patching) causes type checker errors (`[attr-defined]`), poor IDE support (no autocomplete), unclear ownership of data, and fragile code that breaks with framework updates.

**Anti-pattern discovered**: setting custom attributes on Flask Blueprints :

```python
# BAD: Monkey-patching Blueprint with custom attribute
blueprint = Blueprint("biz", __name__, url_prefix="/biz")
blueprint.nav = {  # type: ignore[attr-defined]
    "label": "Marketplace",
    "icon": "shopping-cart",
    "order": 40,
}
```

Problems:
1. `blueprint.nav` doesn't exist on Blueprint class
2. Type checker complains (requires `# type: ignore`)
3. No IDE autocomplete for the dict keys
4. No validation of the configuration

**Solution**: use a registry pattern with a typed configuration function:

```python
# GOOD: Registry pattern with typed function
from app.flask.lib.nav import configure_nav

blueprint = Blueprint("biz", __name__, url_prefix="/biz")
configure_nav(blueprint, label="Marketplace", icon="shopping-cart", order=40)
```

The registry implementation:

```python
# registry.py
class NavConfig(TypedDict, total=False):
    label: str
    icon: str
    order: int
    acl: list[tuple[str, Any, str]]

_NAV_REGISTRY: dict[str, NavConfig] = {}

def configure_nav(
    blueprint: Blueprint,
    *,
    label: str,
    icon: str = "",
    order: int = 99,
    acl: list[tuple[str, Any, str]] | None = None,
) -> None:
    config: NavConfig = {"label": label, "icon": icon, "order": order}
    if acl is not None:
        config["acl"] = acl
    _NAV_REGISTRY[blueprint.name] = config

def get_nav_config(blueprint_name: str) -> NavConfig | None:
    return _NAV_REGISTRY.get(blueprint_name)
```

**Benefits**: type safety, IDE autocomplete, clean separation, backward compatibility, validation.

### Composition Over Inheritance (Applied)

**Rule**: prefer composition / registry over inheritance when you can't (or shouldn't) modify the base class.

When considering how to attach metadata to objects, three approaches exist:

| Approach | Example | Pros | Cons |
|----------|---------|------|------|
| Monkey-patching | `obj.custom = data` | Simple | Type errors, fragile |
| Inheritance | `class NavBlueprint(Blueprint)` | Type-safe | Couples to base class, can't retrofit |
| Composition/Registry | `configure(obj, **data)` | Type-safe, decoupled | Separate lookup needed |

Prefer registry / composition when:
- You can't modify the base class (framework objects).
- The metadata is optional (not all instances need it).
- You want to keep the object's type unchanged.
- You need backward compatibility.

### Stripe Customer = Organisation, not person

**Rule**: a Stripe `Customer` is a billing entity, not a personal account — bind it to the Organisation, not to a User.

A Stripe `Customer` carries `name`, `email`, `address`, `metadata` — it's the legal payer. For B2B SaaS, the right home for `stripe_customer_id` is the Organisation (the entity that pays), not a Subscription row or a User. The current BW Manager accesses the Customer Portal independently of who originally subscribed. Pattern used by Slack, Notion, Linear.

Concretely: avoid `Subscription.stripe_customer_id` as the primary home — it's misleading because Subscriptions come and go, but the Customer should persist across them.

### Denormalize only when write points are finite

**Rule**: a projected (denormalized) column is only safe if you can name a finite set of write sites and cover them.

`Organisation.bw_id` / `Organisation.bw_active` are safe because they're written at *exactly* the BW activation/deactivation points and covered by integration tests. Before introducing a denormalized column, prove you can enumerate the write points.

### Projected data needs a single source of truth

**Rule**: any datum derivable from another must have one representation and one access point.

Before a W11 refactoring, `Organisation.logo` and `BusinessWall.logo` could diverge. The fix : pick one canonical home, wrap reads through a utility function. Same rule applies between `Organisation.type` and the type implicit in the active BW.

### Synthesis spec beats N parallel sources

**Rule**: when multiple analyses cover the same topic, write a synthesis spec that primes over them — don't try to reconcile them pairwise.

Four parallel analyses (two models × analysis + recommendation each) drifted into subtle divergences (FPI vs FAE naming, three different recommended price tables, 3 vs 9 webhook counts). A formal cross-check followed by a single synthesis spec that primes over the sources is more efficient than trying to reconcile the sources against each other pairwise. Banner each older doc with "Updated <date>, see <new>" and explicit cross-refs — otherwise readers continue to treat the older docs as authoritative.

---

## No Mocks Policy

The single most impactful testing principle in this codebase. Most testing pitfalls trace back to overuse of mocks.

### Why Mocks Are Problematic

**Rule**: test real behaviour, not mock interactions.

**Anti-pattern discovered**: tests using `unittest.mock.MagicMock` and `patch`:

```python
# BEFORE: Mock-heavy test that doesn't test real behavior
from unittest.mock import MagicMock, patch

def test_extract_fragment():
    with patch("app.flask.lib.htmx.htmx", MagicMock()):
        result = extract_fragment(html, id="content")
    assert "Content" in result
```

Problems:
1. Tests mock interactions, not real behavior.
2. Mocks can drift from actual implementation.
3. Tests pass even when real code would fail.
4. Violates "State over Behavior" principle.

**Solution**: test the actual logic, bypass the guard check:

```python
# AFTER: Test the logic directly without mocks
def _extract_by_id(html: str, element_id: str) -> str:
    """Extract element by id using the same logic as extract_fragment."""
    try:
        parser = etree.HTMLParser()
        tree = etree.fromstring(html, parser)
        selector = f'//*[@id="{element_id}"]'
        node = tree.xpath(selector)[0]
        return etree.tounicode(node, method="html")
    except Exception:
        return html

def test_extract_by_id() -> None:
    """Test extraction by element id."""
    html = "<html><body><div id='content'>Content</div></body></html>"
    result = _extract_by_id(html, "content")
    assert "Content" in result
```

### When You Think You Need Mocks

**Rule**: every mock has a non-mock alternative — find it before reaching for `MagicMock`.

| Situation | Instead of Mock | Use |
|-----------|-----------------|-----|
| External service (DB, API) | Mock the client | In-memory database, test server |
| Feature flag/guard | Mock the flag | Test the logic directly |
| Time-dependent code | Mock `datetime` | Pass time as parameter |
| Random behavior | Mock `random` | Seed the RNG or inject generator |
| File system | Mock file operations | Use `tmp_path` fixture |

---

## Refactoring Discipline

How to land structural changes without leaving a trail of disabled tests, dead code, or surprised reviewers.

### Two-phase refactor: disable then clean

**Rule**: split a large refactor across two weeks — introduce the new model and disable dependent tests in phase one, drop the old model and re-enable tests in phase two.

The W12 → W14 sequence (introduce `bw_active`/`bw_id`, disable dependent tests in W12, drop the old enum/column and re-enable tests in W14) works better than an atomic swap. An explicit "tests disabled temporarily, re-enable after X is removed" marker in the weekly notes keeps the debt from sleeping.

### Re-enabling disabled tests is a first-class task

**Rule**: schedule the re-enable as a dedicated goal in the next week, not as a vague follow-up.

When a refactor forces test disabling, the "temporary" disable becomes permanent if not promoted to a goal. Confidence in the suite silently erodes.

### Extract a utility on the third use, not the first

**Rule**: two usages → copy. Third usage → factor.

`extract_image_from_request()` was introduced only when the same block appeared identically in articles, communiqués, and events. Premature abstraction (at the second usage) doesn't survive real-world variance.

### Renaming beats a boolean parameter for behaviour switches

**Rule**: rename the function to encode the intent — don't add `active: bool = True`.

`get_business_wall_for_organisation()` → `get_active_business_wall_for_organisation()` revealed call sites that implicitly assumed "active" without checking, plus a few that wanted *any* BW (split into `get_any_business_wall_for_organisation()`). Explicit renaming forces callers to articulate which variant they need.

### Move helpers out of view-transaction wrappers

**Rule**: production code commits at the view layer, never inside service helpers.

The test harness wraps each test in a savepoint, expecting production code to commit only via the test's session. A service helper that calls `db.session.commit()` directly leaks data into the test DB (caught by a `_check_tables_empty` diagnostic at teardown). Move commits to the route entry point; keep service helpers transaction-neutral so tests can call them directly under the test's savepoint.

### Trace the full CI chain before adding a step

**Rule**: read the full workflow → makefile → tool chain before adding a "missing" check.

Tempted to add `ty check` separately to GitHub Actions and SourceHut workflows — both already invoke `make lint`, which already includes `ty check`. Always trace the full chain before adding a redundant step.

### Short spec before each MVP

**Rule**: write a 1-2 page spec before any code on a new feature — it acts as an anchor, not a contract.

Five MVPs landed in one week without scope creep, correlated with each having a short FR spec written before any code. The spec forces a "what's V0 vs vision" arbitration and remains a reusable artifact for client calls.

---

## Testing Strategy

What to test, how to organize, and how to avoid the bulk-tests-low-coverage trap.

### Coverage ≠ Quality

**Rule**: before writing a test, ask "what new code path does this exercise?"

**Problem**: adding many tests without improving coverage means the tests are redundant. During a test improvement effort, 37 tests were added but coverage stayed at 60%. This happened because:

1. Tests duplicated coverage of code already tested.
2. Tests verified the same behavior multiple ways.
3. Tests checked framework behavior (pytz, strftime) instead of application code.

**Lesson**: use coverage reports to identify *untested* code, not just low-coverage files.

### More Tests ≠ Better Tests

**Rule**: fewer, focused tests covering distinct behaviours beat many redundant tests.

After a cleanup, test count went from 1000 → 944, yet coverage stayed the same (60%). The removed tests were duplicates testing the same function from different modules, multiple tests for trivial edge cases (empty list, empty dict as separate tests), and tests verifying third-party library behavior. Apply the "Fewest Elements" rule from Simple Design.

### Don't Test Framework/Library Behavior

**Rule**: trust your dependencies — test *your* code, not theirs.

**Anti-pattern discovered**: tests that verify pytz and strftime work:

```python
# BEFORE: Testing pytz, not our code
def test_format_constant() -> None:
    """Test FORMAT constant is valid strftime format."""
    dt = datetime(2024, 3, 15, 14, 30, 45)
    result = dt.strftime(FORMAT)  # Tests strftime, not our code
    assert "15" in result

def test_localtz_is_valid_timezone() -> None:
    """Test LOCALTZ is a valid pytz timezone."""
    assert LOCALTZ is not None  # Tests pytz, not our code
    dt = datetime(2024, 3, 15, 14, 30, 0)
    localized = LOCALTZ.localize(dt)
    assert localized.tzinfo is not None
```

### Test Business Logic, Not Trivial Accessors

**Rule**: one test per business rule, not one per attribute.

**Anti-pattern**: testing every property individually:

```python
# BEFORE: 5 separate tests for same Snowflake class
def test_snowflake_int_conversion() -> None: ...
def test_snowflake_str_conversion() -> None: ...
def test_snowflake_process_id() -> None: ...
def test_snowflake_worker_id() -> None: ...
def test_snowflake_generation() -> None: ...

# AFTER: One test verifying the class works
def test_snowflake_attributes_and_conversions() -> None:
    """Test Snowflake attributes, int/str conversions, and bounds."""
    flake = snowflakes.Snowflake(0, 12345)

    # Conversions
    assert int(flake) == 12345
    assert str(flake) == "12345"

    # Attribute bounds (the actual business rules)
    assert 0 <= flake.process_id <= 0b11111
    assert 0 <= flake.worker_id <= 0b11111
    assert 0 <= flake.generation <= 0b111111111111
```

### Test All Enum Values in One Test

**Rule**: loop over the enum — don't write one test per value.

```python
# BEFORE: Separate tests for each enum type
def test_make_label_organisation_type() -> None: ...
def test_make_label_bw_type() -> None: ...
def test_make_label_profile() -> None: ...
def test_make_label_all_organisation_types() -> None: ...  # Redundant!
def test_make_label_all_profiles() -> None: ...  # Redundant!

# AFTER: One comprehensive test per enum
def test_make_label_for_all_profiles() -> None:
    """Test make_label works for all ProfileEnum values."""
    for profile in ProfileEnum:
        result = make_label(profile)
        assert result == LABELS_PROFILE[profile]
        assert isinstance(result, str)
```

This pattern automatically catches new enum values without updating tests, verifies the mapping is complete, and uses one test instead of N.

### Avoid Inheritance and Mixins in Tests

**Rule**: tests must be readable in isolation — duplication beats hidden indirection.

**Anti-pattern discovered**: using mixins to share test code across similar modules:

```python
# BAD: Mixin hides test logic in a separate file
class FilterBarTestMixin:
    filter_bar_class: type
    sample_filter_id: str

    def test_add_filter(self) -> None:
        bar = self.create_bar()
        bar.add_filter(self.sample_filter_id, "value")
        assert bar.has_filter(self.sample_filter_id, "value")

class TestWireFilterBar(FilterBarTestMixin):
    filter_bar_class = FilterBar
    sample_filter_id = "sector"

class TestEventsFilterBar(FilterBarTestMixin):
    filter_bar_class = FilterBar
    sample_filter_id = "genre"
```

Problems:
1. **Obscures what's being tested** — must read mixin file to understand test.
2. **Over-engineers simple tests** — adds abstraction where duplication is fine.
3. **Couples unrelated modules** — change to mixin affects all inheritors.
4. **Harder to debug** — stack traces span multiple files.

**Better approach**: keep tests self-contained with acceptable duplication:

```python
# GOOD: Self-contained, readable test file
class TestFilterBarStateManipulation:
    """Test FilterBar state manipulation logic."""

    def _create_bar(self, state: dict | None = None) -> FilterBar:
        """Create a FilterBar with preset state."""
        bar = object.__new__(FilterBar)
        bar.state = state if state is not None else {}
        return bar

    def test_add_filter(self) -> None:
        """Test add_filter appends to filters list."""
        bar = self._create_bar()
        bar.add_filter("sector", "tech")
        assert bar.state["filters"] == [{"id": "sector", "value": "tech"}]
```

Guidelines:
- Each test file should be understandable in isolation.
- A small helper method (`_create_bar`) in each test class is fine.
- Duplication between test files for similar modules is acceptable.
- Test the underlying logic directly (e.g., dictionary manipulation).

### Do Use Parametrization

**Rule**: parametrization is good — inheritance is bad. They are not the same pattern.

```python
# GOOD: Parametrized test - all cases visible in one place
@pytest.mark.parametrize("filter_id,value,expected_tag", [
    ("sector", "tech", "secteur"),
    ("genre", "news", "genre"),
    ("topic", "ai", "rubrique"),
])
def test_active_filters_tag_label(filter_id: str, value: str, expected_tag: str) -> None:
    """Test active_filters returns correct tag_label for each filter type."""
    bar = _create_bar({"filters": [{"id": filter_id, "value": value}]})
    active = bar.active_filters
    assert active[0]["tag_label"] == expected_tag
```

| Parametrization | Inheritance/Mixins |
|-----------------|-------------------|
| Test logic visible in same file | Test logic hidden in parent class |
| All test cases listed together | Must check class hierarchy |
| Easy to add/remove cases | Changes affect all subclasses |
| Clear what's being tested | Abstraction obscures intent |

Use `@pytest.mark.parametrize` when testing the same behavior with different inputs, verifying edge cases (empty, None, boundary values), or testing multiple enum values.

### Test the Underlying Logic

**Rule**: many classes wrap simple logic — test the logic directly, not the framework-coupled wrapper.

```python
# FilterBar's state manipulation is just dictionary operations
# Test the dict operations, not the Flask-dependent class initialization

def test_add_filter(self) -> None:
    bar = self._create_bar()  # Bypass __init__, set state directly
    bar.add_filter("sector", "tech")
    # We're really testing: dict manipulation works correctly
    assert bar.state["filters"] == [{"id": "sector", "value": "tech"}]
```

Benefits: isolates the logic from framework dependencies (Flask session), makes tests faster (no app context needed), focuses on what actually matters (the business logic).

### `b_integration` vs `c_e2e` distinction

**Rule**: any test that hits an HTTP route belongs in `c_e2e/`, even if it covers only an internal detail.

Direct function calls = integration; FlaskClient HTTP = e2e. Otherwise the same surface gets tested on both sides and regressions become ambiguous to locate.

### Avoid Duplicate Test Files for Similar Modules

**Rule**: one test file per pattern, not per instance.

**Anti-pattern discovered**: four separate test files testing nearly identical conversion functions across different KYC field types:

```
tests/a_unit/modules/kyc/test_select_one_free.py      # 11 tests
tests/a_unit/modules/kyc/test_select_multi_optgroup.py # 9 tests
tests/a_unit/modules/kyc/test_select_one.py            # 7 tests
tests/a_unit/modules/kyc/test_lib_utils.py             # Already tested!
```

All four files tested `convert_to_tom_choices_js()` and `convert_to_tom_optgroups_js()` — functions that are nearly identical across modules. Keep one test file that tests the *pattern*. If the functions are truly identical, they should be refactored to share code anyway.

### Consolidate Related Tests

**Rule**: group tests by *behavior*, not by *input variation*.

```python
# BEFORE: 8 separate tests
def test_merge_dicts_simple() -> None: ...
def test_merge_dicts_overwrites_values() -> None: ...
def test_merge_dicts_empty_target() -> None: ...
def test_merge_dicts_empty_other() -> None: ...
def test_merge_dicts_nested() -> None: ...
def test_merge_dicts_deeply_nested() -> None: ...  # Same as nested!
def test_merge_dicts_replace_non_dict_with_dict() -> None: ...
def test_merge_dicts_replace_dict_with_scalar() -> None: ...

# AFTER: 4 focused tests
def test_merge_dicts_flat_and_overwrite() -> None: ...
def test_merge_dicts_nested() -> None: ...
def test_merge_dicts_type_mismatch() -> None: ...
def test_merge_dicts_empty() -> None: ...
```

### A `len(roles) == N` assertion can pin a bug into a regression test

**Rule**: assert the *exact set*, not the count — counts hide semantics.

The Community Role regression (Press Relations users seeing the Newsroom) came from `append_user_role_from_community` adding without removing the previous role. A legacy test asserted exactly that defective state via `assert len(user.roles) == 2`. Prefer asserting the exact set of expected roles, and cross-check the transverse invariant (for each community, the Work menu is watertight).

---

## Common Pitfalls

Specific anti-patterns we've hit. Each is short — the fix is usually a one-liner once you know to look for it.

### Pitfall 1: Testing Internal Implementation Details

**Rule**: test public-API behaviour, not private classes.

**Example**: testing the `Counter` class that's an internal detail of `SnowflakeGenerator`:

```python
# BAD: Tests internal implementation
def test_counter_increment() -> None:
    counter = snowflakes.Counter()
    assert counter.value == 0
    counter.increment()
    assert counter.value == 1
```

**Better**: test the public API behavior that relies on the counter:

```python
# GOOD: Tests the behavior, not the implementation
def test_flakes_are_unique() -> None:
    generator = snowflakes.SnowflakeGenerator()
    count = 10000
    flakes = {generator.generate() for _ in range(count)}
    assert len(flakes) == count  # Counter ensures uniqueness
```

### Pitfall 2: Hardcoding Expected Values

**Rule**: use the source-of-truth constant — don't hardcode a copy.

```python
# BAD: Hardcoded value that changed
assert make_label(OrganisationTypeEnum.COM) == "Communication"  # Wrong!

# GOOD: Use the source of truth
assert make_label(OrganisationTypeEnum.COM) == LABELS_ORGANISATION_TYPE[OrganisationTypeEnum.COM]
```

### Pitfall 3: Testing Empty Collections Separately

**Rule**: one test for "empty input" covers list, dict, set, etc.

```python
# BAD: Two tests for same edge case
def test_empty_list_returns_empty_list() -> None:
    assert convert([]) == []

def test_empty_dict_returns_empty_list() -> None:
    assert convert({}) == []

# GOOD: One test covers the empty case
def test_empty_input() -> None:
    """Test empty collections return empty result."""
    assert convert([]) == []
    assert convert({}) == []
```

### Empty-list filter trap

**Rule**: for "optional" SQL filters, use `if authors:` — not `if authors is not None`.

`if authors is not None` evaluates True for `[]`, then `.where(Model.owner_id.in_([]))` matches nothing — silently. Treat an empty list as "no filter", not as "match nothing".

### Fail fast on date-sensitive tests

**Rule**: pin the date — never depend on `date.today()` in a test.

Several tests passed Monday-Thursday and broke on Friday (ISO week calculations, weekday-of-month). Use `freezegun` or clock injection.

### Anti-spam bypasses are mandatory in mail test harnesses

**Rule**: bypass `is_email_sending_allowed`, `partition_by_cap`, `_recent_dups` / `_over_cap` when in test mode — or reset between tests.

Without explicit short-circuits, looping tests succeed once then silently capture zero mails on the next run.

### Measure coverage in-vivo, not in post-processing

**Rule**: use a live coverage extension during dev — don't rely on offline `coverage report`.

`flask-coverage` (live extension exposing `/debug/coverage/*`) lets you measure after any Playwright sequence without re-running the suite. Much faster than `coverage run + report` for targeting which modules to push.

---

## HTTP & Browser Gotchas

Web-layer surprises that mostly come from browser behaviour (prefetch, cookies, HMR) interacting badly with the server.

### Idempotent GET on confirmation pages

**Rule**: any GET route that creates an object must guard on the **real state**, not a session flag.

`/BW/confirmation/free` created 2 BWs on a single GET — Firefox prefetch on the redirect chain `/activate_free → /confirmation/free` re-fired the handler as long as `session["bw_activated"]` was true. Check whether the entity already exists in DB, not whether the session "thinks" it does.

### Werkzeug 3+ `MAX_FORM_MEMORY_SIZE = 500 KB`

**Rule**: bump `MAX_FORM_MEMORY_SIZE` to ~3× your max image size when accepting base64 uploads.

Rejects cropper.js uploads (1 MB base64-encoded image → ~1.4 MB form field → silent 413). Symptom: photo upload mysteriously fails for ~1 MB images on Werkzeug 3.

### Session-id idempotency guards must verify ownership

**Rule**: a session-stored object id is not proof of ownership — re-validate.

A BW "already existing" referenced by `session["bw_id"]` is not enough. Always validate `is_bw_manager_or_admin(user, existing)` before short-circuiting creation. Otherwise: an orphan BW pointed at by a stale session → success page then unauthorized dashboard for the current user.

### Flask-Security only purges auth keys at login

**Rule**: add an explicit `user_authenticated` handler that scrubs application-prefix session keys.

Application filter state (`events:*`, `wire:*`, `swork:*`, `biz:*` prefixes) persists in the cookie session across user switches on the same browser. Flask-Security only cleans Flask-Login keys.

---

## Email & Notifications

Cross-cutting rules about *when* you send a mail and *who* is on the other end.

### Email-citing-state operations: send first, mutate second

**Rule**: if an email cites state, send it before any mutation that invalidates that state.

`cancel_rdv` resets `contact.date_rdv = None`. The cancellation email body cites the date, so `send_rdv_cancelled_*_email` has an early-return `if contact.date_rdv is None`. The original order (cancel → email) silently dropped the notification.

### Verify "familiar" imports before writing send-mail code

**Rule**: `grep` the repo for the actual mail library before importing what feels obvious.

`flask_mail.Message` is not this project's mail library — it's `flask_mailman`, exposed via `EmailService.send_system_email` in `app/services/emails/`. A "familiar" import would have crashed with `ImportError` on the first `CRON_RUN=1`.

### Couple recipient creation to the notification trigger

**Rule**: any user-input path that must produce a notification later should create (or reference) the recipient entity *in* the form, not downstream in the handler.

The "non-mais" branch of an Avis d'Enquête refusal had a free-text email input that wasn't stored as a Contact — so no notification could be sent later. Replaced with a `<select>` of organisation colleagues, which guarantees a Contact exists when the trigger fires.

### Sender naming: type, not role

**Rule**: name email-related variables by their *type* (`sender_mail`, `sender_full_name`), not by their *role* (`sender_name`).

`sender_name` was ambiguous (person name? technical identifier?). Splitting into `sender_mail` / `sender_full_name` makes the intent explicit at every call site and eliminates the "I put the email in the name field" bug class.

---

## Stripe Integration

Payment-specific rules. Some cross-reference the Architectural Principles section above.

### Prefer event-driven mirroring over short-TTL cache for displayed prices

**Rule**: for any displayed price that leads to payment, never hit the Stripe API at render time.

Any cache window between Stripe's authoritative price and the price Aipress24 displays is a risk that the user pays a different amount than the one shown. A local mirror table fed by `price.created/updated/deleted` webhooks reconciles within seconds; the Stripe Checkout page remains the final authority on what's charged.

### Customer = Organisation (cross-ref)

See [Architectural Principles → Stripe Customer = Organisation](#stripe-customer--organisation-not-person). The home for `stripe_customer_id` is the Organisation, not a Subscription row or a User.

### Production commits at the view layer (cross-ref)

See [Refactoring Discipline → Move helpers out of view-transaction wrappers](#move-helpers-out-of-view-transaction-wrappers). Webhook handlers commit at the route entry point; service helpers stay transaction-neutral so the test harness's savepoint can roll them back cleanly.

---

## SQLAlchemy & ORM Patterns

Type-related and query-related rules specific to SQLAlchemy 2.0 + `Mapped[T]`.

### `Mapped[dict]` vs `Mapped[list]` is not a typing cosmetic

**Rule**: pick the correct collection type — `ty` cascades 15+ errors when wrong.

SQLAlchemy stores both as JSON columns at the DB level, but `ty` rejects list operations (`.append`, indexed iteration) on a `Mapped[dict]` declaration. Verify the actual shape of the value being stored before annotating.

### Compare by ID, not by instance, in `.where()` clauses

**Rule**: `.where(Model.owner_id == user.id)` — never `.where(Model.owner == user)`.

The instance form works by accident (instance identity), but the ID form is explicit, faster (no relationship load), and doesn't break on detached instances. Reflex: always go through the FK column.

### `Mapped[ClassVar[...]]` vs `ClassVar[Mapped[...]]`

**Rule**: for non-mapped class attributes on a model, `ClassVar` goes on the outside.

Inverted, SQLAlchemy tries to map the static value and `ty` produces hard-to-read errors.

### Hybrid property double API

**Rule**: a computed property that must be filterable needs `@hybrid_property` with `.expression`.

A plain `@property` reads in Python but breaks ORM filters. `@hybrid_property` with `.expression` lets `.where(Model.ville == "Paris")` work. Reach for it whenever a computed property needs to be filterable.

---

## Type Checker Hygiene

Rules around `ty` (primary checker), `pyrefly` (complementary), and `mypy` (legacy ignores).

### `case Path(template_path):` is a fake pattern match

**Rule**: never trust a positional `case` pattern on a stdlib type without `__match_args__` — verify in a REPL.

`pathlib.Path` has no `__match_args__`. The `case` raises `TypeError: Path() accepts 0 positional sub-patterns (1 given)` at runtime as soon as the branch is hit. Correct form: `case Path() as template_path:`. Pyrefly catches this, mypy doesn't.

### `aenum.StrEnum` is poorly supported by type checkers

**Rule**: prefer stdlib `enum.StrEnum` (Python 3.11+) over `aenum.StrEnum`.

Pyrefly flags `not-iterable` and `not-a-type` on `aenum.StrEnum` subclasses. Stdlib behaves identically for the common `StrEnum + auto()` case and has first-class type-checker support.

### `type: ignore` outlives the tool that justified it

**Rule**: audit `type: ignore` whenever you change type checkers — and always use `type: ignore[specific-code]`.

Migrating from mypy to ty, 23 ignores were dropped — most dated from old mypy versions or SQLAlchemy patterns long since fixed. The specific-code form makes future audits greppable.

### Liskov violation via heterogeneous return types

**Rule**: unify return types across subclasses — even if "it works".

`get_authors()` returned `list[User]` in one subclass, `None` in another, `Query` in a third — compiles fine, breaks at the call site. Unify to `Iterable[User] | None` to force callers to handle absence.

---

## E2E Testing (Playwright)

Browser-automation-specific gotchas. Most of these cost a half-day of debugging before being understood.

### `page.request.post()` does NOT carry `BrowserContext` cookies

**Rule**: use `page.evaluate("fetch(...)")` or a helper that goes through the JS fetch — and always assert the final URL.

Authenticated POSTs via `page.request.post()` silently bounce on `/auth/login` (status 200, body = login form). Five tests were green false positives until a uniform `/auth/login not in resp["url"]` assertion was added.

### Vite HMR sockets block Firefox e2e beyond ~20 tests

**Rule**: route `**://localhost:3000/**` to `route.abort()` in an autouse fixture when e2e-testing against a dev server.

Vite serves a recursive ES-module graph and opens one HMR WebSocket per page. Firefox's scheduler serializes new scripts behind earlier HMR sockets — DCL stalls indefinitely after ~20 pages. Pages still render their HTML, just without HMR (which tests don't use).

---

## Documentation & Specs

How we structure plans, specs, and weekly notes so they remain useful over time.

### Synthesis spec beats N parallel sources (cross-ref)

See [Architectural Principles → Synthesis spec beats N parallel sources](#synthesis-spec-beats-n-parallel-sources). Write one source-of-truth spec and banner the older ones.

### Short spec before each MVP (cross-ref)

See [Refactoring Discipline → Short spec before each MVP](#short-spec-before-each-mvp). 1-2 pages, written before any code.

---

## Quick Reference: Test Review Checklist

Before merging tests, verify:

- [ ] **Distinct coverage**: does each test exercise different code paths?
- [ ] **No mocks**: are we testing real behavior, not mock interactions?
- [ ] **Tests our code**: are we testing our logic, not framework/library behavior?
- [ ] **Consolidate similar tests**: can related assertions be grouped?
- [ ] **Meaningful**: does the test verify business logic, not trivial accessors?
- [ ] **Self-contained**: can the test file be understood without reading other files?
- [ ] **No inheritance**: are we avoiding mixins/base classes that hide test logic?
- [ ] **Date-pinned if needed**: any date-sensitive logic frozen via `freezegun` or clock injection?
- [ ] **No production commits in helpers**: only the route entry point calls `db.session.commit()`?

---

*Last updated: May 2026*
*Context: Test quality improvement sprint (Jan 2026), navigation registry refactoring (Jan 2026), Stripe finance integration + W4-W20 weekly notes distillation (Feb-May 2026)*
