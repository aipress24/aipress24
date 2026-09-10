# Working Method

Part of [Lessons Learned](00-index.md).

### Reproduce the exact symptom before touching code

**Rule**: a red test emitting the *same* error string as production is the difference between a one-commit fix and a multi-commit thrash.

Every fix that started from an exact reproduction landed in one pass. Every fix that guessed thrashed: a CSS column bug took 4 attempts because the first 3 treated the CSS symptom instead of the unescaped-HTML cause. When you can't reproduce at the unit layer, go *up* a layer (real Jinja env, real browser) rather than guessing.

### An audit's severity labels are unreliable in both directions

**Rule**: an audit — human or agent — produces *leads*, not *severities*. Verify each finding independently before acting on it, or dismissing it.

A fan-out audit **over-graded** ("critical stored XSS" on a premise that was false; "HIGH silent data loss" on idempotent revokes) and **under-graded** ("medium cosmetic" was every admin table rendering as escaped literal text in production; "latent low" was a `KeyError` 500ing the public members directory). Acting on the labels in either direction would have wasted effort *and* shipped breakage.

Be especially wary of "dead code" findings: confirm by execution (set intersections, call-site reachability, a failing characterization test), never by inspection, before deleting.

### The fix must not be worse than the bug

**Rule**: a fix that makes the symptom invisible is a worse bug — now undiagnosable. Never write a test that asserts the broken behaviour.

A blank-page "fix" hid the empty response instead of redirecting to an actionable surface, and a test asserted `response.data == b""`, codifying it. If the only test you can write asserts the symptom, you haven't found the root cause yet.

### Cross-cutting and security fixes carry a follow-up regression budget

**Rule**: a cross-cutting fix is not "done" at merge — budget for a wave of regressions in code paths that quietly depended on the old, lax behaviour.

One correct autoescape fix spawned three downstream bugs over a session. Land such changes early in a cycle, add sentinels at the policy boundary, and watch the error tracker for a week before calling it closed.

### Product decisions get reversed after the first demo

**Rule**: phase delivery so each decision is an independently revertible commit.

Capturing a decision up front does not freeze it — seeing the running result changes minds. Because one feature shipped in 3 independent phases, a reversal touched one filter instead of a monolith.

### Two-phase refactor: disable, then clean

**Rule**: introduce the new model and disable dependent tests in phase one; drop the old model and re-enable tests in phase two.

Better than an atomic swap. Write an explicit "tests disabled, re-enable after X is removed" marker so the debt doesn't sleep — and **schedule the re-enable as a dedicated goal**, not a vague follow-up, or the "temporary" disable becomes permanent and suite confidence silently erodes.

### Extract a utility on the third use, not the first

**Rule**: two usages → copy. Third usage → factor.

Premature abstraction (at the second usage) doesn't survive real-world variance.

### Rename beats a boolean parameter for behaviour switches

**Rule**: encode the intent in the name — don't add `active: bool = True`.

`get_business_wall_for_organisation()` → `get_active_business_wall_for_organisation()` revealed call sites that implicitly assumed "active" without checking, plus a few that wanted *any* BW. Explicit renaming forces callers to articulate which variant they need.

### Trace the full chain before adding a step

**Rule**: read workflow → makefile → tool chain before adding a "missing" check.

`ty check` was nearly added to two CI workflows that both already invoke `make lint`, which already runs it.

### Short spec before each MVP

**Rule**: 1-2 pages before any code — an anchor, not a contract.

Five MVPs landed in one week without scope creep, each preceded by a short spec. It forces a "V0 vs vision" arbitration and remains a reusable artifact for client calls.

### Synthesis spec beats N parallel sources

**Rule**: when several analyses cover one topic, write a synthesis that primes over them — don't reconcile them pairwise.

Four parallel analyses drifted into subtle divergences (inconsistent naming, three different price tables, 3 vs 9 webhook counts). Banner each superseded doc with "Updated <date>, see <new>" — otherwise readers keep treating the old one as authoritative.

### A working-tree scan is not a repository scan

**Rule**: before reporting on a file, ask whether the repository actually carries it. `git ls-files` and the published branches answer; `ls` does not.

A security audit reported an unpinned third-party action running on a workflow holding the deployment token. The workflow was on disk in every working copy — and tracked on no branch, excluded by `.gitignore` under the comment « # Not needed ». GitHub never ran it, so the runner never held that token and the finding was void. The tool listed pipelines from the working tree without checking what was published, and the next scan will find the file again.

The same question applies to any generated, ignored or vendored file a scanner picks up. « It is in my checkout » and « it is in the product » are different claims.

### A probe that reports nothing must first be shown to report something

**Rule**: before believing a measurement that says "zero", run it where the answer is known to be non-zero. A silent zero is the most convincing wrong answer there is.

Chasing an empty targeting screen, a probe reported that every selector offered 0 options — a clean, plausible, entirely false result. It called `hasattr(sel, "get_options")` on a class exposing `options` as a *property*, so the branch never ran and the empty list was the probe's own. Corrected, the same selectors offered 417. The next attempt read `FilterOption.value` on a dataclass whose field is `id`, and failed loudly — which was the lucky case.

An instrument that cannot distinguish "the system returned nothing" from "I asked the wrong question" is not evidence, and it will send you to rewrite code that was never broken.
