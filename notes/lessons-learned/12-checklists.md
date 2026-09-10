# Checklists

Part of [Lessons Learned](00-index.md).

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

### Before declaring a change verified

- [ ] Ran the browser suite **for the module you touched** (`make test-e2e MOD=<module>`), not a subset that happens to be nearby? A KYC change verified with `MOD=regressions` shipped a 500 on the whole sign-up wizard.
- [ ] Does the assertion distinguish success from a 500? Asserting the *absence* of an error message passes against an error page, which has no such message either. Assert the status and one field the page must contain.
- [ ] Called a service getter with no default? `SessionService.get(key)` raises `KeyError`; `dict.get` returns `None`. `x = svc.get(k) or {}` reads safe and is not.
- [ ] Is the template renderable under the test config at all? `WTF_CSRF_ENABLED = False` makes `form.csrf_token` undefined, so any page rendering it cannot be covered below the browser tier without turning CSRF back on.

### Before acting on a bug or a finding

- [ ] Reproduced the exact production error string in a red test?
- [ ] Treated the audit's severity as unverified — reproduced it, or proved "dead code" dead by execution?
- [ ] Is the fix making the symptom invisible rather than removing the cause?
- [ ] Multiple user-correctable failure modes? Return a structured outcome, not `bool`.
- [ ] Calling a repository getter? Confirmed raises-vs-returns-`None`?
- [ ] Counting or filtering A against taxonomy B? Proved both use the same canonical key?
