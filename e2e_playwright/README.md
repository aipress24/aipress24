# Playwright e2e — pre-launch checks

Read-only Playwright tests that exercise the four **go/no-go** sections of `local-notes/plans-2026.md`. Each test logs in with a real account from `local-notes/00-ListeDesProfilsDeTests-7.2.csv` and inspects the running app — local dev server **or** production.

## Run

The self-contained way — nothing to start beforehand:

```bash
make test-e2e                  # whole suite, no DB writes
make test-e2e MOD=kyc          # one module
make test-e2e E2E_ALL=1        # include the mutates_db and slow tests
make test-e2e E2E_PYTEST_ARGS=-q   # dots, not one line per test
```

`run_e2e.py` boots a server on **8899** (so a `make run` dev server stays free
on 5000), waits for it, runs pytest, then stops the server and exits with
pytest's status — a failed suite fails `make`. The server's own output goes to
`e2e_playwright/server.log`, **not** to the terminal, so what you see is pytest
and nothing else. It runs with `FLASK_ACCEPT_ANY_PASSWORD`, so the suite signs
in against any database — including a restored production dump whose hashes
don't match the CSV.

If something goes wrong before the first test, the script prints the tail of
that log for you. `E2E_PORT=8901` runs a second suite alongside a first; the
script refuses to start rather than fight over a busy port.

`mutates_db` is excluded unless `E2E_ALL=1`: those tests write, and the KYC
signup ones create real members. Note that an empty `E2E_MARKERS=""` does
*not* mean "run everything" — `export` hands undefined make variables down as
empty, so empty has to keep meaning "use the default". Hence `E2E_ALL`.

Against a server that is already up — your own `make run`, or production —
set `E2E_BASE_URL`. Nothing is started and nothing is stopped:

```bash
make test-e2e E2E_BASE_URL=http://127.0.0.1:5000
make test-e2e E2E_BASE_URL=https://aipress24.com E2E_MARKERS='not slow'
```

`make test-e2e` is the only e2e rule; `test-e2e-local`, `-prod`, `-attached`
and `-parallel` are gone. Their behaviour lives in the knobs above, and
`E2E_PYTEST_ARGS` covers the rest — `E2E_PYTEST_ARGS='-n 4 --dist=loadfile'`
for the parallel pass, for instance.

## Layout

Tests are grouped by application module so a session can target one layer at a time. Fixtures live in the root `conftest.py` and are inherited by every subdir.

```
e2e_playwright/
├── conftest.py            # shared fixtures (login, profile, mail_outbox, …)
├── admin/      test_admin_coverage.py
├── bw/         test_bw_coverage.py + test_bw_lifecycle.py + test_bw_wizard.py
├── common/     test_all_profiles_smoke.py + test_authorization_matrix.py
│                + test_communities.py + test_deep_navigation.py
│                + test_functional_coverage.py
├── infra/      test_mail_harness.py + test_upload_limits.py
├── kyc/        test_kyc_smoke.py + test_kyc_widgets.py
│                + test_kyc_inscription.py
├── security/   test_auth_flows.py
├── wip/        test_avis_lifecycle.py + test_wip_lifecycle.py + test_wip_subpages.py
└── wire/       test_paywall_ui.py
```

New module dirs (`swork/`, `biz/`, `events/`, `stripe/`, `notifications/`, `preferences/`, `public/`, `api/`) are added as the plan in `local-notes/plans/e2e-tests-playwright.md` progresses.

## Test layers

| Sub-dir | Layer | Mode |
|---|---|---|
| `security/test_auth_flows.py` | auth | read-only |
| `common/test_communities.py` | menu visibility | read-only |
| `common/test_authorization_matrix.py` | URL gates (negative) | read-only |
| `common/test_functional_coverage.py` | URL gates (positive) | read-only |
| `common/test_deep_navigation.py` | deep GET crawl | read-only |
| `common/test_all_profiles_smoke.py` | credential smoke | read-only, **slow** |
| `kyc/test_kyc_smoke.py` | KYC routes render | read-only (1 `mutates_db`) |
| `kyc/test_kyc_widgets.py` | tom-select widgets, taxonomies reach the browser | read-only |
| `kyc/test_kyc_inscription.py` | signup tunnel per community + refusals | mutates_db |
| `infra/test_mail_harness.py` | `/debug/mail/*` smoke | read-only |
| `infra/test_upload_limits.py` | upload size limit | read-only |
| `wire/test_paywall_ui.py` | paywall surface | read-only |
| `wip/test_wip_subpages.py` | WIP detail pages | read-only |
| `wip/test_wip_lifecycle.py` | publish/unpublish toggle | mutates_db |
| `wip/test_avis_lifecycle.py` | RDV state machine multi-user | mutates_db |
| `bw/test_bw_coverage.py` | BW URL surfaces | read-only |
| `bw/test_bw_lifecycle.py` | partnership + role-invitation lifecycles | mutates_db |
| `bw/test_bw_wizard.py` | full free-activation wizard | mutates_db |
| `admin/test_admin_coverage.py` | admin URL surfaces | mostly read-only |

## Markers

- `slow` — long-running (the 169-profile smoke). Excluded by default; `E2E_ALL=1` includes it.
- `mutates_db` — tests that perform writes. Excluded by default; `E2E_ALL=1` includes them. `_block_db_writes_on_prod` in `conftest.py` also skips them when `--base-url` names production — but it matches on the hostname only, so it does **not** fire on a local server holding a production copy.

Run a single file manually :

```bash
pytest -v --browser chromium --base-url=http://127.0.0.1:5000 \
    e2e_playwright/common/test_authorization_matrix.py
```

## Test profiles

The CSV holds 169 profiles. The `profile()` fixture picks the first non-broken account in a community ; the `profile_smoke` parametrized fixture iterates over every row. Three accounts are listed in `KNOWN_BROKEN` (stored credentials don't match the CSV) and skipped from any login-dependent test.

The suite **does not seed** these accounts. They must already exist on the target with the password listed in the CSV. If the very first probe fails, the whole suite is skipped with one actionable message — point `--base-url` at production or seed the dev DB out-of-band so its passwords match `FLASK_SECURITY_PASSWORD_SALT`.

## Browser

**Chromium is the default.** Measured back to back on an idle machine:

| module | chromium | firefox | webkit |
|---|---|---|---|
| `kyc` (26 tests) | **14 s** | 29 s | hangs |
| `wire` (21 tests) | **43 s** | 72 s | — |

Roughly twice as quick, green on both. Firefox also stalls on the aborted
Vite module graph (see `_abort_vite_dev_assets`), which is its own pathology
and not something the suite can fix.

**WebKit hangs**: 240 s on a three-test module without running a single one.
Not investigated further — use it only if you are chasing a Safari-specific
bug, and expect to debug the harness first.

```bash
make test-e2e E2E_BROWSER=firefox     # or webkit, at your peril
```

Anything engine-specific in a test is a bug in the test: pin what the widget
reports (`select.tomselect.isOpen`, `ts.dropdown_content`), not how an engine
happens to hide a dropdown.

## Coverage

The dev server registers the [`flask-coverage`](https://pypi.org/project/flask-coverage/) extension when `app.debug` is on (or `FLASK_COVERAGE_PASSWORD` is set), exposing a live coverage dashboard at <http://127.0.0.1:5000/debug/coverage/>. Use it to see which lines of `src/app/` actually execute under the e2e suite.

Workflow :

1. Start the dev server with coverage tracing from the very first import (so module-level lines count too) :

   ```bash
   COVERAGE_PROCESS_START=$(pwd)/pyproject.toml make run
   ```

   Without that env var the tracer only starts after `create_app` returns, so view bodies are still measured but module-level imports are not.

2. Run the e2e suite to drive traffic :

   ```bash
   make test-e2e E2E_ALL=1
   ```

3. Inspect the dashboard live :
   - <http://127.0.0.1:5000/debug/coverage/> — text report + links
   - <http://127.0.0.1:5000/debug/coverage/html/> — per-file source w/ line highlighting
   - `POST /debug/coverage/snapshot` to flush counters to disk
   - `POST /debug/coverage/reset` between runs to clear

Coverage scope is `src/app` with the same omits as the unit-test runs (`tests/`, `**/*test.py`, `src/app/faker/**`) — see `[tool.coverage.run]` in `pyproject.toml`. The extension is fail-closed : in prod (no debug, no password) `register_coverage` is a no-op even if the package is installed.
