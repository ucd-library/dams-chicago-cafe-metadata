#!/usr/bin/env python3
"""
Mint real EZID ARKs for the collection + every item, and substitute them for the
ark:/PLACEHOLDER/<id> values in the JSON-LD.

Reads credentials from .env (EZID_USERNAME, EZID_PASSWORD, EZID_SHOULDER).
Idempotent: minted ARKs are recorded in arks/ark_map.json; a re-run reuses
existing ARKs and only mints for ids not yet in the map (so it never
double-mints). Substitution always re-applies from the map.

EZID API: POST https://ezid.cdlib.org/shoulder/<shoulder>  (HTTP basic auth)
  body: anvl metadata; response: "success: ark:/<naan>/<id>"

Usage:
  python3 mint_arks.py            # mint missing + substitute
  python3 mint_arks.py --dry-run  # show what would be minted, mint nothing
"""
import base64
import glob
import json
import os
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent
ARK_MAP = REPO / "arks" / "ark_map.json"
EZID = "https://ezid.cdlib.org"


def load_env():
    env = {}
    p = REPO / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    for k in ("EZID_USERNAME", "EZID_PASSWORD", "EZID_SHOULDER"):
        env.setdefault(k, os.environ.get(k, ""))
    return env


def anvl(d):
    def esc(s):
        return s.replace("%", "%25").replace("\n", "%0A").replace(":", "%3A")
    return "\n".join(f"{esc(k)}: {esc(v)}" for k, v in d.items())


def mint_one(shoulder, user, pw, target_meta):
    url = f"{EZID}/shoulder/{shoulder}"
    body = anvl(target_meta).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "text/plain; charset=UTF-8")
    tok = base64.b64encode(f"{user}:{pw}".encode()).decode()
    req.add_header("Authorization", f"Basic {tok}")
    with urllib.request.urlopen(req, timeout=60) as r:
        resp = r.read().decode("utf-8").strip()
    if not resp.startswith("success:"):
        raise RuntimeError(f"EZID error: {resp}")
    return resp.split(":", 1)[1].strip().split("|")[0].strip()  # "ark:/.../..."


def collect_ids():
    ids = ["__collection__"]
    ids += [Path(f).name[:-len(".jsonld.json")] for f in glob.glob(str(REPO / "items" / "*.jsonld.json"))]
    return ids


def main():
    dry = "--dry-run" in sys.argv
    env = load_env()
    if not dry and not (env["EZID_USERNAME"] and env["EZID_PASSWORD"] and env["EZID_SHOULDER"]):
        sys.exit("Missing EZID_USERNAME / EZID_PASSWORD / EZID_SHOULDER (.env). Aborting.")

    ARK_MAP.parent.mkdir(exist_ok=True)
    ark_map = json.loads(ARK_MAP.read_text()) if ARK_MAP.exists() else {}

    ids = collect_ids()
    to_mint = [i for i in ids if i not in ark_map]
    print(f"{len(ids)} ids total; {len(to_mint)} need minting; {len(ark_map)} already minted.")
    if dry:
        print("DRY RUN — nothing minted. First 5 to mint:", to_mint[:5])
        return

    for i, item_id in enumerate(to_mint, 1):
        meta = {"_profile": "dc", "_target": "", "dc.publisher": "UC Davis Library",
                "dc.title": "Chicago Cafe Records" if item_id == "__collection__" else item_id}
        ark = mint_one(env["EZID_SHOULDER"], env["EZID_USERNAME"], env["EZID_PASSWORD"], meta)
        ark_map[item_id] = ark
        if i % 25 == 0 or i == len(to_mint):
            ARK_MAP.write_text(json.dumps(ark_map, indent=2))
            print(f"  minted {i}/{len(to_mint)}")
    ARK_MAP.write_text(json.dumps(ark_map, indent=2))

    # ---- substitute placeholders ----
    def sub_identifiers(node, item_id):
        ark = ark_map.get(item_id)
        if not ark:
            return False
        ids_list = node.get("schema:identifier", [])
        changed = False
        for k, v in enumerate(ids_list):
            if isinstance(v, str) and v.startswith("ark:/PLACEHOLDER/"):
                ids_list[k] = ark
                changed = True
        return changed

    n = 0
    for f in glob.glob(str(REPO / "items" / "*.jsonld.json")):
        item_id = Path(f).name[:-len(".jsonld.json")]
        node = json.loads(Path(f).read_text())
        if sub_identifiers(node, item_id):
            Path(f).write_text(json.dumps(node, indent=2, ensure_ascii=False))
            n += 1
    cf = REPO / "collection" / "chicago-cafe.jsonld.json"
    cnode = json.loads(cf.read_text())
    if sub_identifiers(cnode, "__collection__"):
        cf.write_text(json.dumps(cnode, indent=2, ensure_ascii=False))
    print(f"Substituted real ARKs into {n} items + collection.")


if __name__ == "__main__":
    main()
