# Playwright e2e — pre-launch checks

Read-only Playwright tests that exercise the four **go/no-go** sections of `local-notes/plans-2026.md`. Each test logs in with a real account from `local-notes/cards/attachments/00-ListeDesProfilsDeTests-7.2.csv` and inspects the running app — local dev server **or** production.

## Run

```bash
# Local dev server, quick (skips slow smoke)
make test-e2e-local            # http://127.0.0.1:5000

# Local dev server, full (includes 169-profile login smoke, ~10 min)
make test-e2e-local-full

# Single module — much faster, default MOD=wip
make test-e2e MOD=bw           # or: common, infra, wip, wire, admin, security

# Production, quick
PROD_URL=https://aipress24.com make test-e2e-prod

# Production, full (149+ logins against prod — heavy but read-only)
PROD_URL=https://aipress24.com make test-e2e-prod-full
```

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
├── security/   test_auth_flows.py
├── wip/        test_avis_lifecycle.py + test_wip_lifecycle.py + test_wip_subpages.py
└── wire/       test_paywall_ui.py
```

New module dirs (`kyc/`, `swork/`, `biz/`, `events/`, `stripe/`, `notifications/`, `preferences/`, `public/`, `api/`) are added as the plan in `local-notes/plans/e2e-tests-playwright.md` progresses.

## Test layers

| Sub-dir | Layer | Mode |
|---|---|---|
| `security/test_auth_flows.py` | auth | read-only |
| `common/test_communities.py` | menu visibility | read-only |
| `common/test_authorization_matrix.py` | URL gates (negative) | read-only |
| `common/test_functional_coverage.py` | URL gates (positive) | read-only |
| `common/test_deep_navigation.py` | deep GET crawl | read-only |
| `common/test_all_profiles_smoke.py` | credential smoke | read-only, **slow** |
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

- `slow` — long-running (the 169-profile smoke). Skipped from `make test-e2e-local` / `test-e2e-prod`. Included in the `-full` variants.
- `mutates_db` — tests that perform writes. Auto-skipped against the prod target (see `_block_db_writes_on_prod` in `conftest.py`).

Run a single file manually :

```bash
pytest -v --browser firefox --base-url=http://127.0.0.1:5000 \
    e2e_playwright/common/test_authorization_matrix.py
```

## Test profiles

The CSV holds 169 profiles. The `profile()` fixture picks the first non-broken account in a community ; the `profile_smoke` parametrized fixture iterates over every row. Three accounts are listed in `KNOWN_BROKEN` (stored credentials don't match the CSV) and skipped from any login-dependent test.

The suite **does not seed** these accounts. They must already exist on the target with the password listed in the CSV. If the very first probe fails, the whole suite is skipped with one actionable message — point `--base-url` at production or seed the dev DB out-of-band so its passwords match `FLASK_SECURITY_PASSWORD_SALT`.

## Browser

Default browser is Firefox (matches `Makefile` targets). To use Chromium:

```bash
pytest -v --browser chromium e2e_playwright
```

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
   make test-e2e-local-full
   ```

3. Inspect the dashboard live :
   - <http://127.0.0.1:5000/debug/coverage/> — text report + links
   - <http://127.0.0.1:5000/debug/coverage/html/> — per-file source w/ line highlighting
   - `POST /debug/coverage/snapshot` to flush counters to disk
   - `POST /debug/coverage/reset` between runs to clear

Coverage scope is `src/app` with the same omits as the unit-test runs (`tests/`, `**/*test.py`, `src/app/faker/**`) — see `[tool.coverage.run]` in `pyproject.toml`. The extension is fail-closed : in prod (no debug, no password) `register_coverage` is a no-op even if the package is installed.
