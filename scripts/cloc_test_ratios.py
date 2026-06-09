#!/usr/bin/env python3
"""Compare LOC of test packages vs. their corresponding source packages.

Walks every source unit under `src/app/` and pairs it with its
counterparts under `tests/a_unit/`, `tests/b_integration/`, and
`tests/c_e2e/`. Reports a sorted table of test/source LOC ratios with
summary stats and outliers.

A "source unit" is :

- each sub-package of `src/app/modules/` (one per module : biz, wire,
  wip, …) — these are usually the meatiest pieces of the app,
- every top-level sub-package of `src/app/` that holds code (services,
  lib, models, flask, faker, ui, …) — each treated as one unit.

Counterpart paths mirror the source layout : `src/app/modules/biz/`
maps to `tests/<tier>/modules/biz/` for tier in (a_unit,
b_integration, c_e2e). Missing test dirs are reported as 0 LOC.

Run :

    uv run python scripts/cloc_test_ratios.py
    uv run python scripts/cloc_test_ratios.py --json   # machine-readable
    uv run python scripts/cloc_test_ratios.py --min-src 50  # filter tiny units

Requires `cloc` on PATH.
"""

from __future__ import annotations

import argparse
import json
import shutil
import statistics
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = ROOT / "src" / "app"
TEST_TIERS: tuple[str, ...] = ("a_unit", "b_integration", "c_e2e")
TIER_ROOTS = {tier: ROOT / "tests" / tier for tier in TEST_TIERS}

# Packages we don't expect to test, by policy. Keep this short — every
# entry should have a stated reason so future readers can challenge it.
DEFAULT_EXCLUDE: frozenset[str] = frozenset(
    {
        # Seed/fake-data generator, exercised end-to-end every time the
        # test suite spins up a fixture — no need to test it directly.
        "faker",
        # Dev-time CLI utilities (`flask job bano`, `make nlp`, …).
        # None of the 5 `Job` subclasses here are scheduled or invoked
        # from production code — `reputation` is a manual duplicate of
        # what `actors/reputation.py` already does on cron. Treated as
        # the CLI sibling of `faker/`.
        "jobs",
    }
)


@dataclass
class Row:
    """One source unit + its three tiers of tests."""

    name: str
    src_loc: int
    tier_loc: dict[str, int] = field(default_factory=dict)

    @property
    def total_test_loc(self) -> int:
        return sum(self.tier_loc.values())

    @property
    def ratio(self) -> float:
        return self.total_test_loc / self.src_loc if self.src_loc else 0.0


def cloc_loc(path: Path) -> int:
    """Return the Python `code` LOC under `path` as counted by cloc.
    Returns 0 if the path doesn't exist."""
    if not path.exists():
        return 0
    try:
        proc = subprocess.run(
            ["cloc", "--json", "--quiet", "--include-lang=Python", str(path)],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        print(
            f"cloc failed on {path}: {exc.stderr.strip()}",
            file=sys.stderr,
        )
        return 0
    if not proc.stdout.strip():
        # cloc prints nothing for empty inputs ; treat as 0.
        return 0
    data = json.loads(proc.stdout)
    python = data.get("Python")
    if not python:
        return 0
    return int(python.get("code", 0))


def discover_source_units() -> list[tuple[str, Path]]:
    """List (display_name, source_path) pairs."""
    units: list[tuple[str, Path]] = []

    # 1. One unit per module under src/app/modules/.
    modules_dir = SRC_ROOT / "modules"
    if modules_dir.exists():
        for sub in sorted(modules_dir.iterdir()):
            if sub.is_dir() and not sub.name.startswith("_"):
                units.append((f"modules/{sub.name}", sub))

    # 2. Top-level subpackages of src/app/ (skip modules, which we
    # already broke out).
    for sub in sorted(SRC_ROOT.iterdir()):
        if not sub.is_dir() or sub.name.startswith("_"):
            continue
        if sub.name in {"modules", "templates", "static", "__pycache__"}:
            continue
        units.append((sub.name, sub))

    return units


def test_paths_for(rel_name: str) -> dict[str, Path]:
    """Map the source unit name to its three tier paths."""
    return {tier: TIER_ROOTS[tier] / rel_name for tier in TEST_TIERS}


def build_rows(min_src: int, exclude: frozenset[str]) -> list[Row]:
    rows: list[Row] = []
    for name, path in discover_source_units():
        if name in exclude:
            continue
        src_loc = cloc_loc(path)
        if src_loc < min_src:
            continue
        tier_paths = test_paths_for(name)
        tier_loc = {tier: cloc_loc(tier_paths[tier]) for tier in TEST_TIERS}
        rows.append(Row(name=name, src_loc=src_loc, tier_loc=tier_loc))
    return rows


def format_table(rows: list[Row]) -> str:
    """Render a fixed-width table sorted by ratio descending."""
    rows_sorted = sorted(rows, key=lambda r: r.ratio, reverse=True)

    headers = ("package", "src", "a_unit", "b_integ", "c_e2e", "tests", "ratio")
    keys = ("src_loc", "a_unit", "b_integration", "c_e2e", "total_test_loc")

    name_w = max(len(headers[0]), max(len(r.name) for r in rows_sorted))
    num_widths: list[int] = []
    for h, key in zip(headers[1:-1], keys, strict=True):
        col_vals = [
            r.tier_loc[key] if key in TEST_TIERS else getattr(r, key)
            for r in rows_sorted
        ]
        num_widths.append(max(len(h), max(len(f"{v:,}") for v in col_vals)))
    ratio_w = max(len(headers[-1]), len("99.99x"))

    widths = [name_w, *num_widths, ratio_w]
    sep_line = "  ".join("-" * w for w in widths)

    header_line = "  ".join(
        f"{h:<{widths[0]}}" if i == 0 else f"{h:>{widths[i]}}"
        for i, h in enumerate(headers)
    )

    body_lines = []
    for r in rows_sorted:
        body_lines.append(
            "  ".join(
                [
                    f"{r.name:<{widths[0]}}",
                    f"{r.src_loc:>{widths[1]},}",
                    f"{r.tier_loc['a_unit']:>{widths[2]},}",
                    f"{r.tier_loc['b_integration']:>{widths[3]},}",
                    f"{r.tier_loc['c_e2e']:>{widths[4]},}",
                    f"{r.total_test_loc:>{widths[5]},}",
                    f"{r.ratio:>{widths[6] - 1}.2f}x",
                ]
            )
        )
    return "\n".join([header_line, sep_line, *body_lines])


def summary(rows: list[Row]) -> str:
    """Aggregate stats : totals, weighted+plain averages, outliers."""
    if not rows:
        return "(no rows)"

    total_src = sum(r.src_loc for r in rows)
    total_tests = sum(r.total_test_loc for r in rows)
    by_tier = {
        tier: sum(r.tier_loc.get(tier, 0) for r in rows) for tier in TEST_TIERS
    }

    plain_ratios = [r.ratio for r in rows]
    mean = statistics.mean(plain_ratios)
    median = statistics.median(plain_ratios)
    stdev = statistics.stdev(plain_ratios) if len(plain_ratios) > 1 else 0.0
    weighted = total_tests / total_src if total_src else 0.0

    # Buckets, picked empirically rather than via Tukey fences (the
    # distribution is bimodal — modules with rich suites cluster ~1.5x,
    # peripheral packages cluster ~0x — and IQR fences don't surface
    # either tail usefully).
    UNTESTED, UNDER, OVER = 0.0, 0.5, 2.0
    untested = [r for r in rows if r.total_test_loc == 0]
    under = [r for r in rows if 0 < r.ratio < UNDER]
    over = [r for r in rows if r.ratio > OVER]

    lines = [
        "",
        "=== Summary ===",
        f"Source units analysed : {len(rows)}",
        f"Total source LOC      : {total_src:,}",
        f"Total test LOC        : {total_tests:,}",
        "  a_unit              : {a_unit:,}".format(**by_tier),
        "  b_integration       : {b_integration:,}".format(**by_tier),
        "  c_e2e               : {c_e2e:,}".format(**by_tier),
        f"Weighted test/src     : {weighted:.2f}x  (Σ tests / Σ src)",
        f"Plain mean ratio      : {mean:.2f}x  ± {stdev:.2f}",
        f"Median ratio          : {median:.2f}x",
    ]

    def _list(title: str, items: list[Row]) -> None:
        if not items:
            return
        lines.append("")
        lines.append(title)
        for r in sorted(items, key=lambda x: x.src_loc, reverse=True):
            lines.append(
                f"  - {r.name:<28}  src={r.src_loc:>6,}  "
                f"tests={r.total_test_loc:>6,}  ratio={r.ratio:5.2f}x"
            )

    _list(f"No tests at all ({len(untested)} units) :", untested)
    _list(
        f"Under-tested (0 < ratio < {UNDER:.1f}x — {len(under)} units) :",
        under,
    )
    _list(
        f"Heavily-tested (ratio > {OVER:.1f}x — {len(over)} units) :",
        over,
    )
    return "\n".join(lines)


def emit_json(rows: list[Row]) -> str:
    """Machine-readable dump : same data as the table, but as JSON."""
    return json.dumps(
        [
            {
                "name": r.name,
                "src_loc": r.src_loc,
                "tier_loc": r.tier_loc,
                "total_test_loc": r.total_test_loc,
                "ratio": round(r.ratio, 4),
            }
            for r in sorted(rows, key=lambda r: r.ratio, reverse=True)
        ],
        indent=2,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--min-src",
        type=int,
        default=20,
        help="Skip source units smaller than this LOC (default 20).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of the human-readable table.",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="NAME",
        help=(
            "Skip this source unit (repeatable). On top of the built-in "
            f"exclusions: {sorted(DEFAULT_EXCLUDE)}."
        ),
    )
    args = parser.parse_args()
    exclude = DEFAULT_EXCLUDE | frozenset(args.exclude)

    if shutil.which("cloc") is None:
        print("cloc not found on PATH — install it first.", file=sys.stderr)
        return 2

    rows = build_rows(min_src=args.min_src, exclude=exclude)
    if not rows:
        print("(no source units passed the min-src filter)", file=sys.stderr)
        return 1

    if args.json:
        print(emit_json(rows))
        return 0

    print(format_table(rows))
    print(summary(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
