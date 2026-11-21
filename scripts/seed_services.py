#!/usr/bin/env python3
"""Seed/upsert the service catalogue from automation/portals/<id>/service.json (contract v1.6).

Preserves the `active` flag of services that already exist. Prints only ids and counts.
Usage:  python3 scripts/seed_services.py [--dry-run]
"""
import json, os, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COLS = ["id", "name", "name_ml", "category", "tier", "submission", "fields", "documents", "fee", "active", "notes"]


def load_env():
    for line in (ROOT / ".cloud.env").read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def call(method, path, body=None, prefer=None):
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    h = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if prefer:
        h["Prefer"] = prefer
    req = urllib.request.Request(os.environ["SUPABASE_URL"] + "/rest/v1" + path,
                                 data=json.dumps(body).encode() if body is not None else None, headers=h, method=method)
    with urllib.request.urlopen(req) as r:
        t = r.read()
        return json.loads(t) if t else None


def main():
    load_env()
    dry = "--dry-run" in sys.argv
    files = sorted((ROOT / "automation" / "portals").glob("*/service.json"))
    existing = {s["id"]: s for s in call("GET", "/services?select=id,active")}
    rows, problems = [], []
    for f in files:
        s = json.loads(f.read_text())
        for fld in s.get("fields", []):
            if fld.get("type") == "select" and not fld.get("options"):
                problems.append(f"{s['id']}.{fld['key']}: select without options")
            if "aadhaar" in fld["key"].lower() and "last4" not in fld["key"].lower():
                problems.append(f"{s['id']}.{fld['key']}: Aadhaar field not allowed")
        row = {c: s.get(c) for c in COLS}
        row["active"] = existing[s["id"]]["active"] if s["id"] in existing else s.get("active", True)
        rows.append(row)
    if problems:
        print("REFUSING to seed:", *problems, sep="\n  ")
        sys.exit(1)
    print(f"{len(rows)} services from files; {sum(r['id'] in existing for r in rows)} existing, "
          f"{sum(r['id'] not in existing for r in rows)} new")
    if not dry:
        call("POST", "/services?on_conflict=id", rows, prefer="resolution=merge-duplicates,return=minimal")
        print("seeded:", ", ".join(r["id"] for r in rows))


if __name__ == "__main__":
    main()
