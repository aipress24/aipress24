# Playwright e2e — pre-launch checks

Read-only Playwright tests that exercise the four **go/no-go** sections of `local-notes/plans-2026.md`. Each test logs in with a real account from `local-notes/cards/attachments/00-ListeDesProfilsDeTests-7.2.csv` and inspects the running app — local dev server **or** production.

## Run

```bash
# Local dev server (default in pytest-playwright config)
make test-e2e-local            # http://127.0.0.1:5000

# Production (read-only, no purchases / signups / uploads)
PROD_URL=https://aipress24.com make test-e2e-prod
```

## Safety on production

Tests are split between **read-only** (safe everywhere) and **mutating** (forbidden against prod):

| File | Mode | Notes |
|---|---|---|
| `test_communities.py` | read-only | login + menu visibility + a couple of endpoint probes per community |
| `test_auth_flows.py` | read-only | login + logout + password-reset *form* (no token consumption) |
| `test_paywall_ui.py` | read-only | renders paywalled-article aside + asserts buy buttons are wired (no click-through to Stripe) |
| `test_upload_limits.py` | mutating | **skipped on prod** — exercises BW gallery upload at 1/5/30/50 MB |

The fixture `block_mutations_on_prod` raises if a test marked `mutating` is run with `--base-url` pointing at production.

## Test profiles

The CSV holds 169 profiles. Each test picks one or two representatives of a community via `e2e_playwright/conftest.py::profile()`. Update the CSV when accounts rotate ; do **not** hard-code credentials in tests.

## Browser

Default browser is Firefox (matches `Makefile` targets). To use Chromium:

```bash
pytest -v --browser chromium e2e_playwright
```
