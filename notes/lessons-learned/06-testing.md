# Testing

Part of [Lessons Learned](00-index.md).

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
