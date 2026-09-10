# Security & Trust Boundaries

Part of [Lessons Learned](00-index.md).

### Client-side sanitisation is not a security boundary

**Rule**: sanitise on write *and* escape on render. One layer is a single point of failure.

A rich-text editor renders HTML in the browser, but an attacker POSTs raw HTML directly — the editor is never in that path. Treating its output as trusted-and-`|safe` was a stored-XSS vector. The fix was defence in depth: autoescape on render, a `|sanitize` filter, and a `SanitizedHTML` `TypeDecorator` scrubbing on write, plus a back-fill migration.

### Session-id idempotency guards must verify ownership

**Rule**: an object id stored in the session is not proof of ownership — re-validate before short-circuiting.

An orphan BW referenced by a stale `session["bw_id"]` produced a success page followed by an unauthorized dashboard.

### Flask-Security only purges auth keys at login

**Rule**: add a `user_authenticated` handler that scrubs application-prefix session keys.

Filter state under `events:*`, `wire:*`, `swork:*`, `biz:*` persists across user switches in the same browser; Flask-Security cleans only Flask-Login keys.

The fix was a hand-written list of prefixes, and a hand-written list rots: `newsroom:` — the avis d'enquête targeting filters and the sujet list state — was added by two modules and cleared by none, so the defect came back one module later. A ciblage screen filtering on someone else's criteria shows the new occupant nobody, with no visible cause. The guard is now a test that walks the source for `"<module>:<key>"` literals and fails on any prefix the list does not carry, so a module that invents a prefix fails in CI rather than in a shared browser.

### A record fetched by id must obey the rule its list obeys

**Rule**: whatever clause narrows a list view, the by-primary-key fetch has to apply the same one. Put it in the base fetch, not in each route.

`BaseWipView._get_model` was `repo.get(id)`. The list beside it filtered on `owner_id == user.id`. So every route reaching a record by id — view, edit, and the `post` that saves it — served another member's record to anyone the module gate let in, and overwrote it on save. Confirmed by exploit: a second journalist read and rewrote a rival's avis d'enquête, owner unchanged, and could publish it under their name.

What makes this a rule rather than a bug report is the count. The same defect had already been found and fixed **four times** in this repository, each time locally: the marketplace item detail (#0133), the Sujet visibility gate labelled « VULN-001 », the Event'Room accreditation screens, and `_require_author` on Article. Four local fixes, no shared control, and the fifth instance was waiting in three other modules. `OwnedRepository.get_owned` already existed; nobody called it.

Answer `NotFound`, not `Forbidden`: a redirect confirms the id is real.

### An uploaded filename decides the Content-Type it is served as

**Rule**: allowlist the stored extension, and allowlist again the types the media route is willing to name. Never a denylist.

`create_file_object` took `Path(original_filename).suffix` verbatim into the storage name, and `/media/<name>` derived the response type from that name with `mimetypes.guess_type`. A member naming their upload `.svg` — or `.html`, which is worse and easy to forget — chose the type the browser would be told to trust, on the application's own origin, under the viewer's session. Nothing re-encoded the bytes: the two Pillow helpers that would have (`resized`, `squared`) had no callers at all, and the fields named `ValidImageField` declare no validators.

Two locks, because the first cannot reach what is already stored. And a test pinning that the two lists agree — an extension we keep must map to a type the route will serve, and none of those may be executable.
