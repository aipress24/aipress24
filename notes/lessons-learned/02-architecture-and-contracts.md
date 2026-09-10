# Architecture & Contracts

Part of [Lessons Learned](00-index.md).

### Registry pattern over monkey-patching

**Rule**: never monkey-patch framework objects with custom attributes — use a typed registry.

```python
# BAD — needs `# type: ignore[attr-defined]`, no autocomplete, no validation
blueprint.nav = {"label": "Marketplace", "icon": "shopping-cart", "order": 40}

# GOOD
configure_nav(blueprint, label="Marketplace", icon="shopping-cart", order=40)
```

The registry keeps a `TypedDict` config in a module-level dict keyed by blueprint name.

### Composition over inheritance for metadata

**Rule**: prefer a registry when you can't modify the base class, when the metadata is optional, or when the object's type must stay unchanged.

Inheritance (`class NavBlueprint(Blueprint)`) is type-safe but couples to the base class and can't be retrofitted.

### Denormalize only when write points are finite

**Rule**: a projected column is only safe if you can name every write site and cover it.

`Organisation.bw_id` / `bw_active` are safe because they're written at exactly the BW activation/deactivation points. Conversely, the events mirror can carry denormalized geo columns because `event_receiver` is its single write path — the KYC profile and marketplace offers cannot, since their forms write from several places.

### Projected data needs a single source of truth

**Rule**: anything derivable from something else gets one representation and one access point.

`Organisation.logo` and `BusinessWall.logo` could diverge. Pick one canonical home, wrap reads in a utility.

### Collapsing a structured outcome into `bool` swallows the actionable part

**Rule**: when a function can fail for several distinct, user-correctable reasons, return an enum or dataclass — never `bool`.

`invite_user_role` returned `True/False`; the route discarded the reason. A user typed an email outside the org, saw the modal close, assumed success — the invitation was silently dropped. **"Silent success" is the worst failure mode: nobody files a bug, they just lose data.**

### Know whether your accessor raises or returns None

**Rule**: the raises-vs-returns-`None` contract is part of the signature. Confirm it at the call site; don't infer it from the name.

`repo.get(id)` raises `NotFoundError`; `repo.get_one_or_none(id=…)` returns `None`. Code assuming the second while calling the first turned a normal "not found" into an unhandled 500.

There is a third answer, and it is the nastiest: **the sentinel leaks**. `SessionService.get(key)` used a private `_marker` default to tell "absent" from "stored `None`", and returned that marker to the caller when the session existed but the key did not — so `svc.get(k) or {}` read as safe, and `svc.get(k)` handed back an object no caller could name. It raised only when the session itself was empty, which is why it surfaced as a 500 on the sign-up wizard and nowhere else. An accessor has three possible contracts, not two; the sentinel must never cross the boundary.

### Unify return types across subclasses

**Rule**: a Liskov violation compiles fine and breaks at the call site.

`get_authors()` returned `list[User]` in one subclass, `None` in another, `Query` in a third. Unify to `Iterable[User] | None` to force callers to handle absence.

### Filtering across two datasets requires one canonical key space

**Rule**: prove both sides use the same key *before* trusting a join, filter, or count.

A "0 everywhere" or "nothing filtered" symptom is almost always a key-space mismatch — qualified `"Parent / Child"` vs bare, code vs label, trimmed vs raw — not a logic bug.

### Stripe Customer = Organisation, not person

**Rule**: bind `stripe_customer_id` to the Organisation — the legal payer — not to a User or a Subscription row.

Subscriptions come and go; the Customer persists across them, and the current BW Manager accesses the portal regardless of who originally subscribed.

### A filter that falls back to "everything" must run last

**Rule**: when one filter escapes to the unfiltered population if too few rows match, every narrowing that must always hold has to be applied before it — otherwise the escape is computed on a population the next step will empty.

The ciblage pool ran the thematic pre-filter first, then removed journalists. The pre-filter's floor — « fewer than five matches, return the whole active pool » — was cleared by journalists alone on a sector where they dominated; the exclusion then took every one of them away and left nothing. The screen was empty for every sector unless « include journalists » was ticked, which is precisely what two reporters described.

Swapping the two lines fixes it, and the fix is invisible when the box is ticked, because the exclusion is then the identity. Note what this costs to test: on a base where journalists are a minority the bug does not reproduce, so the regression test has to build the population that triggers it. The browser test written alongside passed with and without the fix, and said nothing.
