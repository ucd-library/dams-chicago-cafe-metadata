#!/usr/bin/env python3
"""
Apply per-item FAST subjects to the generated item JSON-LD.

Reads all fast/proposals/proposals_*.json (each: {item_id: [phrase, ...]}),
resolves every phrase to an authoritative FAST heading via fast_lookup.resolve
(cached), and merges the resulting schema:about entries into each
items/<id>.jsonld.json WITHOUT disturbing the content-type facet term already
present (dedups by @id). Phrases that don't resolve are logged and skipped.
"""
import glob
import json
from pathlib import Path

from fast_lookup import resolve, _load_cache, _save_cache

REPO = Path(__file__).resolve().parent

# Map common proposed phrasings to their authorized FAST forms (verified via the API).
ALIASES = {
    "Chinese American cooking": "Cooking, Chinese",
    "Chinese cooking": "Cooking, Chinese",
    "Mahjong": "Mah jong",
    "World War, 1939-1945": "World War (1939-1945)",
    "Floats (Parades)": "Parade floats",
    "Bass (Fish)": "Bass fishing",
    "Picnicking": "Picnics",
}


def main():
    proposals = {}
    for f in glob.glob(str(REPO / "fast" / "proposals" / "proposals_*.json")):
        for item_id, phrases in json.load(open(f)).items():
            proposals.setdefault(item_id, [])
            for p in phrases:
                p = ALIASES.get(p, p)
                if p not in proposals[item_id]:
                    proposals[item_id].append(p)

    cache = _load_cache()
    unresolved = {}
    applied = 0
    for item_id, phrases in proposals.items():
        node_path = REPO / "items" / f"{item_id}.jsonld.json"
        if not node_path.exists():
            continue
        node = json.loads(node_path.read_text())
        about = node.get("schema:about", [])
        have = {a.get("@id") for a in about}
        for phrase in phrases:
            hit = resolve(phrase, cache=cache, save=False)
            if not hit:
                unresolved.setdefault(phrase, 0)
                unresolved[phrase] += 1
                continue
            if hit["@id"] not in have:
                about.append({"@id": hit["@id"]})  # id-only, per current DAMS convention
                have.add(hit["@id"])
        node["schema:about"] = about
        node_path.write_text(json.dumps(node, indent=2, ensure_ascii=False))
        applied += 1
    _save_cache(cache)

    # Rebuild collection labels (id -> display name) for every FAST term in use.
    # Names come from the content-type facet + the resolver cache, since items
    # store id-only references.
    from build_collection import CT_PHOTOGRAPHS, CT_MENUS, CT_EPHEMERA
    id2name = {c["@id"]: c["schema:name"] for c in (CT_PHOTOGRAPHS, CT_MENUS, CT_EPHEMERA)}
    for v in cache.values():
        if v:
            id2name[v["@id"]] = v["schema:name"]
    label_map = {}
    for f in glob.glob(str(REPO / "items" / "*.jsonld.json")):
        for a in json.load(open(f)).get("schema:about", []):
            if a["@id"] in id2name:
                label_map[a["@id"]] = id2name[a["@id"]]
    labels = [{"@id": "", "@context": {"ucdlib": "http://digital.ucdavis.edu/schema#"},
               "@type": ["ucdlib:LabelService", "ucdlib:Service"]}]
    labels += [{"@id": k, "http://schema.org/name": v} for k, v in sorted(label_map.items())]
    (REPO / "collection" / "chicago-cafe" / "labels.jsonld.json").write_text(
        json.dumps(labels, indent=2, ensure_ascii=False))

    print(f"Applied FAST subjects to {applied} items; {len(label_map)} distinct FAST terms in collection.")
    if unresolved:
        print(f"\nUnresolved phrases ({len(unresolved)}):")
        for p, n in sorted(unresolved.items(), key=lambda x: -x[1]):
            print(f"  {n:3d}  {p}")


if __name__ == "__main__":
    main()
