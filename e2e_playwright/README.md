# Playwright e2e — pre-launch checks

Read-only Playwright tests that exercise the four **go/no-go** sections of `local-notes/plans-2026.md`. Each test logs in with a real account from `local-notes/cards/attachments/00-ListeDesProfilsDeTests-7.2.csv` and inspects the running app — local dev server **or** production.

## Run

```bash
# Local dev server, quick (skips slow smoke)
make test-e2e-local            # http://127.0.0.1:5000

# Local dev server, full (includes 169-profile login smoke, ~10 min)
make test-e2e-local-full

# Production, quick
PROD_URL=https://aipress24.com make test-e2e-prod

# Production, full (149+ logins against prod — heavy but read-only)
PROD_URL=https://aipress24.com make test-e2e-prod-full
```

## Test layers

| File | Layer | Mode | Notes |
|---|---|---|---|
| `test_auth_flows.py` | auth | read-only | login + logout + password-reset *form* (no token consumption) |
| `test_communities.py` | menu visibility | read-only | sidebar matrix per community (5 communities × 3 labels) |
| `test_authorization_matrix.py` | URL gates (negative) | read-only | `/wip/newsroom`, `/wip/comroom`, `/admin/` reject the wrong audience |
| `test_functional_coverage.py` | URL gates (positive) | read-only | each community can open every common surface (Wire, Events, Biz, Swork, …) plus its own authoring space |
| `test_paywall_ui.py` | paywall surface | read-only | renders paywalled-article aside + asserts buy buttons are wired (no click-through to Stripe) |
| `test_upload_limits.py` | upload size limit | read-only | targets `/tests/upload` (drains body, no DB write) ; verifies a small upload succeeds and an oversized one returns 413 |
| `test_all_profiles_smoke.py` | credential smoke | read-only, **slow** | logs in *every* CSV profile (~5 minutes) |

## Markers

- `slow` — long-running (the 169-profile smoke). Skipped from `make test-e2e-local` / `test-e2e-prod`. Included in the `-full` variants.

Run a single layer manually :

```bash
pytest -v --browser firefox --base-url=http://127.0.0.1:5000 \
    e2e_playwright/test_authorization_matrix.py
```

## Test profiles

The CSV holds 169 profiles. The `profile()` fixture picks the first non-broken account in a community ; the `profile_smoke` parametrized fixture iterates over every row. Three accounts are listed in `KNOWN_BROKEN` (stored credentials don't match the CSV) and skipped from any login-dependent test.

The suite **does not seed** these accounts. They must already exist on the target with the password listed in the CSV. If the very first probe fails, the whole suite is skipped with one actionable message — point `--base-url` at production or seed the dev DB out-of-band so its passwords match `FLASK_SECURITY_PASSWORD_SALT`.

## Browser

Default browser is Firefox (matches `Makefile` targets). To use Chromium:

```bash
pytest -v --browser chromium e2e_playwright
```
