# Templates & Rendering

Part of [Lessons Learned](00-index.md).

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
