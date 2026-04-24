#!/usr/bin/env python
# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Login-check all test profiles against a running AiPRESS24 instance.

Reads the test-profile list from
`local-notes/cards/attachments/00-ListeDesProfilsDeTests-7.2.csv`
and POSTs credentials to `/auth/login` on the target host. No
browser, no JS — just `httpx` with CSRF handling. Writes a CSV
report and prints a digest to stdout.

Usage:
    uv run python scripts/check_test_profiles.py \\
        [--base https://aipress24.com] \\
        [--sleep 3] [--section Journalistes] [--limit 5]

    # Tail only (analyse an existing report):
    uv run python scripts/check_test_profiles.py --analyse

Exit code : non-zero if any profile fails to log in.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CSV = (
    ROOT / "local-notes" / "cards" / "attachments"
    / "00-ListeDesProfilsDeTests-7.2.csv"
)
DEFAULT_REPORT = ROOT / "scripts" / "check_test_profiles.report.csv"

UA = "aipress24-profile-check/1.0"
CSRF_RE = re.compile(
    r'name="csrf_token"[^>]*value="([^"]+)"', flags=re.IGNORECASE
)
CATEGORY_RE = re.compile(
    r"^(Journalistes|PR Agency|Academics|Transformers|Leaders & Experts)"
)


# ------------------------------------------------------------------ parsing


def parse_profiles(csv_path: Path) -> list[dict]:
    rows: list[dict] = []
    section = "?"
    with csv_path.open(encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            first = row[0].strip()
            m = CATEGORY_RE.match(first)
            if m:
                section = m.group(1)
                continue
            if first == "Prénom":
                continue
            if len(row) < 6:
                continue
            # Strip on metadata columns, not on the password — a stray
            # leading space in the CSV may match exactly what's stored
            # in the DB (see Aïcha Benmahfoud).
            prenom, nom, fonction, org, mail = (c.strip() for c in row[:5])
            pw = row[5]
            if not mail or "@" not in mail:
                continue
            rows.append(
                {
                    "section": section,
                    "name": f"{prenom} {nom}",
                    "fonction": fonction,
                    "org": org,
                    "email": mail,
                    "password": pw,
                }
            )
    return rows


# ------------------------------------------------------------------ login


def check_one(base: str, email: str, password: str) -> dict:
    login_url = f"{base.rstrip('/')}/auth/login"
    with httpx.Client(
        timeout=20, follow_redirects=False, headers={"User-Agent": UA}
    ) as client:
        try:
            r = client.get(login_url)
        except httpx.RequestError as e:
            return {"ok": False, "stage": "net", "detail": str(e)[:80]}
        if r.status_code not in (200, 302):
            return {
                "ok": False,
                "stage": "GET /auth/login",
                "status": r.status_code,
            }
        m = CSRF_RE.search(r.text)
        if not m:
            return {"ok": False, "stage": "csrf-token-missing"}

        try:
            post = client.post(
                login_url,
                data={
                    "csrf_token": m.group(1),
                    "email": email,
                    "password": password,
                    "next": "",
                    "submit": "Login",
                },
            )
        except httpx.RequestError as e:
            return {"ok": False, "stage": "POST", "detail": str(e)[:80]}

        if post.status_code == 302:
            dest = post.headers.get("location", "")
            if "/auth/login" in dest or dest.endswith("/login"):
                return {"ok": False, "stage": "redirect-loop", "dest": dest}
            return {"ok": True, "dest": dest}
        if post.status_code == 200:
            return {"ok": False, "stage": "form-reshown", "status": 200}
        return {"ok": False, "stage": "POST", "status": post.status_code}


# ------------------------------------------------------------------ main run


def run_sweep(args: argparse.Namespace) -> list[list[str]]:
    rows = parse_profiles(Path(args.csv))
    if args.section:
        rows = [r for r in rows if r["section"] == args.section]
    if args.limit:
        rows = rows[: args.limit]

    started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(
        f"Started at {started} : {len(rows)} profile(s), target {args.base}, "
        f"sleep {args.sleep}s"
    )

    out: list[list[str]] = []
    stats = {"ok": 0, "ko": 0}
    for i, profile in enumerate(rows, 1):
        result = check_one(args.base, profile["email"], profile["password"])
        ok = result["ok"]
        stats["ok" if ok else "ko"] += 1
        out.append(
            [
                profile["section"],
                profile["name"],
                profile["email"],
                "OK" if ok else "KO",
                result.get("stage", ""),
                str(result.get("status", result.get("detail", ""))),
                result.get("dest", ""),
            ]
        )
        mark = "✓" if ok else "✗"
        print(
            f"  [{i:3d}/{len(rows)}] {mark}  "
            f"{profile['section'][:12]:12s}  "
            f"{profile['email'][:50]:50s}  {result.get('stage', '')}"
        )
        if i < len(rows):
            time.sleep(args.sleep)

    with Path(args.report).open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            ["section", "name", "email", "result", "stage", "status", "dest"]
        )
        w.writerows(out)

    print(
        f"\nDone. OK={stats['ok']}  KO={stats['ko']}  -> {args.report}"
    )
    return out


# ------------------------------------------------------------------ digest


def digest(report_path: Path) -> int:
    if not report_path.exists():
        print(f"no report at {report_path}", file=sys.stderr)
        return 2
    rows = list(csv.DictReader(report_path.open(encoding="utf-8")))
    by_section: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_section[r["section"]].append(r)

    total = len(rows)
    ok = sum(1 for r in rows if r["result"] == "OK")
    ko = total - ok
    print(f"TOTAL : {total}   OK={ok}   KO={ko}")

    print("\nBy section:")
    for section, group in by_section.items():
        ok_s = sum(1 for r in group if r["result"] == "OK")
        print(f"  {section:18s}  OK={ok_s:3d} / {len(group):3d}")

    failures = [r for r in rows if r["result"] == "KO"]
    if failures:
        print("\nFailure stages:")
        for stage, n in Counter(r["stage"] for r in failures).most_common():
            print(f"  {stage:20s}  {n}")
        print("\nFirst 20 failures:")
        for r in failures[:20]:
            print(
                f"  {r['section'][:12]:12s}  {r['email'][:50]:50s}  "
                f"stage={r['stage']}  status={r['status']}"
            )

    dests = Counter(r["dest"] for r in rows if r["result"] == "OK")
    if dests:
        print("\nPost-login destinations (top 5):")
        for dest, n in dests.most_common(5):
            print(f"  {n:3d}  {dest}")

    return 0 if ko == 0 else 1


# ------------------------------------------------------------------ CLI


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="https://aipress24.com")
    p.add_argument("--csv", default=str(DEFAULT_CSV))
    p.add_argument("--report", default=str(DEFAULT_REPORT))
    p.add_argument("--sleep", type=float, default=3.0)
    p.add_argument("--section", default=None, help="Filter to one section")
    p.add_argument("--limit", type=int, default=0, help="0 = no limit")
    p.add_argument(
        "--analyse",
        action="store_true",
        help="Skip the sweep, just digest the existing report.",
    )
    args = p.parse_args(argv)

    if args.analyse:
        return digest(Path(args.report))

    run_sweep(args)
    return digest(Path(args.report))


if __name__ == "__main__":
    sys.exit(main())
