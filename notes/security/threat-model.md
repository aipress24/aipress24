# Threat model: AIpress24

*Drafted by bruce on 2026-09-09 from the 490-file scope listing, with ~30 files read in detail. Sources: `notes/adr/003-navigation-acl-and-magic-roles.md`, `notes/adr/004-public-api-data-access-and-sdk.md`, `local-notes/code-reviews/2026-05-03-security-review.md`. Reviewed by Stefane Fermigier, 2026-09-09. Revised the same day after the first audit.*

## System

AIpress24 is a multi-tenant SaaS platform for the French press ecosystem. Members sign up through a KYC questionnaire that places them in one of five communities (presse & médias, communicants, leaders & experts, transformers, académiques), and act on behalf of an organisation that may hold a paid *Business Wall*. They publish articles, press releases, events and calls for contribution; they commission work from one another; they buy and sell paid content and subscriptions through Stripe.

A Flask application serves 245 routes plus a token-authenticated JSON API, backed by PostgreSQL, Redis/Dramatiq for background work, Typesense for search, and S3/MinIO for media.

**The deployment path is not recorded in this repository.** `fly.toml`, `hop3.toml` and the `Dockerfile` are all present and none of them is currently used. Nothing here says which environment variables production sets, which matters because four invariants below turn on one (`ACCEPT_ANY_PASSWORD`, `UNSECURE`, `FLASK_STRIPE_DEBUG_PASSWORD`, `STRIPE_WEBHOOK_SECRET`). An audit can prove the gate is written correctly; it cannot prove the variable is unset in production.

**Kind: service.** Members are not operators. They belong to competing organisations and to communities with different rights, so a signed-in user is a potential adversary against every other user — this is the assumption that sets the severity of everything below.

Administrators are members too. The ADMIN role is held by member accounts, not by a separate operator identity outside the application, so the administrator surface is reachable from inside the system rather than only from a console.

## Assets

- **Members' personal data.** The KYC profile holds identity, photograph, telephone, employer, function and sector. Targeting and accreditation screens list people by name, photo, function and organisation.
- **Editorial integrity.** Who published what, on whose behalf, and whether it was reviewed. A false attribution is the platform's core product failing.
- **Revenue and subscription state.** Stripe customers, paid-article access, Business Wall activation.
- **Non-public editorial intent.** A call for contribution, a commission, an unpublished draft: knowing what a competitor is working on has value.
- **Credentials.** Stripe keys, the Fly deploy token, the Slack bot token, SMTP and S3 credentials, the database.
- **Code execution**, on a CI runner or in production.

## Adversaries

- **A signed-in member of another organisation.** Can reach every authenticated route. Wants other members' data, competitors' drafts and commissions, and paid content they have not bought.
- **A signed-in member of the same organisation with a lesser role.** BWPRi / BWPRe against BW_OWNER: wants to publish, target or decide in their organisation's name.
- **An organisation's own administrator, acting beyond their organisation.** In the model by decision, 2026-09-09. A BW_OWNER or mission holder legitimately governs their own Business Wall; what they must not reach is another organisation's members, drafts or subscription state.
- **A member holding the platform ADMIN role.** Everything behind `/admin/` is theirs by design, and the database export is the sharpest instrument there: it hands over every member's KYC profile in one file. The question the audit asks is not whether they can use it, but whether anything short of ADMIN reaches it, and whether its use leaves a trace.
- **An anonymous visitor.** Reaches sign-up, login, public pages and the Stripe webhook endpoint.
- **Anyone who can POST to `/webhook`.** The endpoint is public by construction. Wants to forge a payment or a subscription activation.
- **Anyone who can open a pull request**, reaching the CI/CD pipeline. The repository is public, so this is the whole internet — though the project does not expect an outside PR to ever arrive. What they get is narrower than it looks: GitHub withholds every secret from a fork's `pull_request` run and issues a read-only token regardless of repository settings, so a fork PR reaches neither the Slack token nor repository write. The adversary who *does* reach those is a **collaborator whose branch runs in-repo**, or whoever controls an action the workflow calls.
- **Whoever controls a direct or transitive dependency**, reaching build and install time on every developer machine and every runner.

## Trust boundaries

| Boundary | What crosses it | Validated where |
|---|---|---|
| Browser → Flask | Form posts, query strings, HTMX fragments, uploads | WTForms validators; `authenticate_user` then `doorman.check_access` in `flask/hooks.py` |
| Browser → API v1 | JSON, `Authorization: Bearer` | `api_v1/__init__.py` `before_request`: token resolved, capability scope required per resource |
| Stripe → `/webhook` | Signed event payloads | `stripe.Webhook.construct_event` in `modules/stripe/views/webhook.py:186` |
| Uploads → S3/MinIO | Images (banner, BW stage B1, articles), ODS spreadsheets (ontology) | `lib/image_utils.py`; the ODS path is a form upload parsed server-side |
| App → shell | `pg_dump` for the admin DB export (`modules/admin/db_export_service.py:173`) | operator-only route behind `/admin/` |
| App → SMTP | Recipient addresses and rendered templates | `services/emails` |
| Dependencies → build | `pdm-backend`, the full `uv.lock` tree | lockfile only |

## Entry points

| Surface | Reachable by | Notes |
|---|---|---|
| `/admin/*` | ADMIN only | Doorman prefix rule, `flask/doorman.py:82`. Includes the DB export. |
| `/wip/*` (Newsroom, Comroom, Event'Room) | Authenticated members | Authoring, commissioning, targeting, accreditation decisions. The richest surface and the one where cross-organisation reads matter most. |
| `/kyc/*` | Anonymous (sign-up) and members (modify) | Wizard writes the profile; `/kyc/modify` re-opens it. Ontology-driven select fields. |
| `/swork`, `/wire`, `/biz`, `/events` | Members; some pages anonymous | Directories, feeds, marketplace, event announcements. |
| `/api/*` (API v1) | Bearer token holders | Scoped per resource. Discovery endpoint is unauthenticated by design (ADR 004). |
| `/webhook` (Stripe) | Anyone on the internet | Signature-verified. Drives paid-article access and BW activation. |
| `/tests/*` | Any authenticated member | Gated on authentication alone — no role check. |
| `/queue/*` (dashboard) | see module | Background-job dashboard. |
| `/debug/stripe/*`, mail debug | Operator, only when the extension registers | Fail-closed double gate; see Out of scope. |
| Dramatiq actors | Whatever enqueues them | Scheduled: grouped notification delivery, event reminders, Stripe mirror sync. |
| `flask` CLI | Operator on the host | Several commands shell out (`db2.py`, `data.py`, `bootstrap.py`). |
| `.github/workflows/ci.yml`, `tests.yml`, `lint.yml` | Anyone who can open a PR (`on: [push, pull_request]`) | `lint.yml` references `secrets.SLACK_BOT_TOKEN`. No `permissions:` block in any workflow. |
| ~~`.github/workflows/fly-deploy.yml`~~ | — | **Not an entry point.** The file exists in working copies but is not tracked on any branch (`.gitignore`, « # Not needed »), so GitHub never runs it and no runner ever held `FLY_API_TOKEN` through it. Listed here because a working-tree scan finds it and will find it again. If the secret was ever created in the repository settings it still exists and still needs revoking — a secret does not depend on a workflow to be there. |
| `/media/<sha256>[.ext]` | Any authenticated member | A content-addressed read of every uploaded file: knowing the hash *is* the access control, and the stored extension used to decide the Content-Type served. |
| `pyproject.toml` build backend (`pdm-backend`) | Whoever controls a dependency | Runs at install time. |

## Invariants

1. A request to `/admin/` without the ADMIN role reaches no handler.
2. Every module blueprint requires an authenticated user before dispatch; anonymous requests reach only the routes that opt out.
3. A member reaches a WIP record only if the module's list would show it to them. `BaseWipView._get_model` enforces it for every route that fetches by id, and answers `NotFound` rather than `Forbidden` so a refusal does not confirm the record exists. A view that legitimately shows more widens the rule by overriding `_can_access`; the default is the owner alone.
4. A Stripe event changes no subscription, no payment and no access grant until `construct_event` has verified its signature against `STRIPE_WEBHOOK_SECRET`.
5. `ACCEPT_ANY_PASSWORD` accepts every password for every account, and refuses to start unless `UNSECURE` is also set. One variable cannot open every account.
6. The debug extensions do not register unless `app.debug` is true or their own password variable is set, and `init_app` re-checks the same gate rather than trusting the caller.
7. User-supplied text reaches templates through Jinja2 autoescaping. The eight `|safe` sites render HTML the server composed (page layout, pagebar), never a member's own text — a `|safe` on `biz/projects/detail.j2` was removed as a stored-XSS vector, and the comment marking it is still there.
8. An event's `access_details` is readable only by a member accredited to that event.
8b. An uploaded file is never served as a type a browser executes. The stored extension comes from an allowlist, and `/media` refuses to name a type outside its own.
9. A KYC select accepts the current taxonomy's values plus the values that profile already held — nothing else.
10. Every database query that returns another member's rows is scoped by organisation, community targeting, or an explicit publication status.

## Out of scope

- **A compromised host.** If the container or the database server is owned, nothing in this model holds. Not defended against here.
- **The deployment configuration.** `fly.toml`, `hop3.toml` and the `Dockerfile` are in the tree and none is in use; how the application actually reaches production is not recorded here, so no invariant resting on an environment variable can be checked from this repository.
- **The `stripe_debug` and `mail_debug` extensions in a development environment.** Accepted risk, reviewed 2026-05-03: the gate is fail-closed in code, and the danger is an operator setting `FLASK_STRIPE_DEBUG_PASSWORD` somewhere internet-reachable, which is operator discipline rather than a code defect. The same review recorded that with that flag on, `construct_event` skips HMAC verification while `/webhook` stays public.
- **Denial of service and HTTP rate limiting.** Outbound email has a quota (`services/emails/email_limiter.py`); nothing throttles login, sign-up or the webhook. Accepted for now, 2026-09-09 — a deliberate deferral, not an assessment that it is harmless. Revisit before the platform is widely known.
- **Self-XSS, and attacks requiring the victim to paste content into their own console.** *(bruce's guess — nobody has contradicted it.)*
- **The seeded development database and its fixtures**, including the profiles CSV used by the e2e suite. *(bruce's guess — nobody has contradicted it.)*
- **`/tests/*`**, gated on authentication alone with no role check. Whether that blueprint belongs in production is a configuration decision, not an invariant of the code. Confirmed 2026-09-09.

## Always reported anyway

Committed secrets, injection into a shell or SQL or a template, memory unsafety, hand-rolled cryptography, and authentication that can be skipped outright — whether or not this model has an adversary who reaches them.
