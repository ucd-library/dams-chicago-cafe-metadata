#!/usr/bin/env python3
"""
Build the Chicago Cafe (D-822) DAMS collection as a fin-filesystem tree.

Reads the three source CSVs + a manifest of the master TIFFs, filters to rows
marked "Good for digital collection", joins CSV metadata to the real master
files, and emits the `collection/` + `items/` JSON-LD serialization that
`fin io import` consumes (format verified against dams-tibbetts-photo-metadata
and dams-byers-metadata).

NOTE on identifiers: this build uses PLACEHOLDER ARKs (ark:/PLACEHOLDER/<id>)
so the full tree can be reviewed before real EZID ARKs are minted. Re-run
mint step later to substitute real ARKs.

Stdlib only. No network. No TIFF bytes needed (only filenames from the manifest).
"""
import csv
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
SRC = REPO / "source_csv"
COLLECTION_SLUG = "chicago-cafe"
COLLECTION_ID = "D-822"
GOOD = "Good for digital collection"

# Master tree, relative to D-822_Chicago_Cafe_Records on the digitization server.
MASTER_ROOT = "D-822_Chicago_Cafe_Records"

CONTEXT = {
    "ldp": "http://www.w3.org/ns/ldp#",
    "schema": "http://schema.org/",
    "fedora": "http://fedora.info/definitions/v4/repository#",
    "webac": "http://fedora.info/definitions/v4/webac#",
    "acl": "http://www.w3.org/ns/auth/acl#",
    "ucdlib": "http://digital.ucdavis.edu/schema#",
    "ebucore": "http://www.ebu.ch/metadata/ontologies/ebucore/ebucore#",
}

LICENSE = "http://rightsstatements.org/vocab/InC-NC/1.0/"  # TODO confirm rights statement
PUBLISHER = {
    "@id": "http://id.loc.gov/authorities/names/no2008108707",
    "schema:name": "UC Davis, Archives and Special Collections",
}

# Content-type facet (the Photos vs Menus/Ephemera filter the user asked for, via schema:about).
# Authoritative OCLC FAST headings (resolved via fast_lookup.py).
CT_PHOTOGRAPHS = {"@id": "http://id.worldcat.org/fast/1061684", "schema:name": "Photographs"}
CT_MENUS = {"@id": "http://id.worldcat.org/fast/1016875", "schema:name": "Menus"}
CT_EPHEMERA = {"@id": "http://id.worldcat.org/fast/1919921", "schema:name": "Ephemera"}


def load_manifest():
    """Return dict: set_name -> sorted list of relative tif paths."""
    sets = {"Grouped": [], "Loose": [], "Photos": []}
    for line in (SRC / "masters_manifest.txt").read_text().splitlines():
        line = line.strip()
        if not line.endswith(".tif"):
            continue
        for s in sets:
            if line.startswith(f"Chicago_Cafe_{s}/"):
                sets[s].append(line)
                break
    for s in sets:
        sets[s].sort()
    return sets


def read_rows(path, divider_text=None):
    """Read a source CSV; stop at a divider row if given; skip blank-name rows.
    Returns list of dicts keyed by the source headers."""
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("Abridged File Name") or "").strip()
            if divider_text and name.lower().startswith(divider_text.lower()):
                break
            # also stop if the first cell equals the divider (name may be blank on divider row)
            first = (list(row.values())[0] or "").strip().lower()
            if divider_text and first.startswith(divider_text.lower()):
                break
            if not name:
                continue
            rows.append(row)
    return rows


YEAR_RE = re.compile(r"(1[89]\d{2}|20\d{2})")


def extract_year(*texts):
    """Return first plausible 4-digit year found, else None."""
    for t in texts:
        if not t:
            continue
        m = YEAR_RE.search(t)
        if m:
            return m.group(1)
    return None


def content_type_for(title):
    """Menus vs other ephemera, for the grouped/loose sets."""
    return [CT_MENUS] if "menu" in (title or "").lower() else [CT_EPHEMERA]


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def media_container():
    return {
        "@context": CONTEXT, "@id": "", "@type": ["ldp:DirectContainer"],
        "ldp:hasMemberRelation": {"@id": "schema:associatedMedia"},
        "ldp:isMemberOfRelation": {"@id": "schema:encodesCreativeWork"},
        "ldp:membershipResource": {"@id": "@base:.."},
    }


def image_list_container():
    return {
        "@context": CONTEXT, "@id": "",
        "@type": ["ucdlib:ImageList", "ldp:DirectContainer", "schema:MediaObject"],
        "schema:name": "Image List",
        "ldp:hasMemberRelation": {"@id": "schema:hasPart"},
        "ldp:isMemberOfRelation": {"@id": "schema:isPartOf"},
        "ldp:membershipResource": {"@id": ""},
    }


def tif_sidecar(position):
    return {"@context": {"schema": "http://schema.org/"}, "@id": "", "schema:position": position}


def build_item(item_id, title, item_type, tif_relpaths, date_raw, description, content_subjects, box_folder):
    """item_type: 'single' (ImageObject) or 'multi' (Book/ArchivalGroup).
    tif_relpaths: ordered list of master-relative tif paths for this item.
    Returns (item_node, list_of_(dest_relpath_in_repo, sidecar_obj), first_image_basename)."""
    images_dir = Path("items") / item_id / "media" / "images"
    sidecars = []
    basenames = [Path(p).name for p in tif_relpaths]
    for i, bn in enumerate(basenames, start=1):
        sidecars.append((images_dir / f"{bn}.jsonld.json", tif_sidecar(f"{i:02d}")))

    node = {"@context": CONTEXT, "@id": ""}
    if item_type == "multi":
        node["@type"] = ["schema:Book", "schema:CreativeWork",
                         "http://fedora.info/definitions/v4/repository#ArchivalGroup"]
    else:
        node["@type"] = ["schema:CreativeWork", "schema:ImageObject"]

    node["schema:name"] = title
    node["schema:associatedMedia"] = {"@id": "@base:/media/images"}
    if basenames:
        node["schema:image"] = {"@id": f"@base:/media/images/{basenames[0]}"}

    ident = [f"ark:/PLACEHOLDER/{item_id}", COLLECTION_ID, item_id]
    if box_folder and box_folder.strip().lower() not in ("digital only", "double check", ""):
        ident.append(f"Box:Folder {box_folder.strip()}")
    node["schema:identifier"] = ident

    node["schema:license"] = {"@id": LICENSE}

    if description and description.strip():
        node["schema:description"] = description.strip()

    year = extract_year(date_raw)
    if year:
        node["schema:datePublished"] = {"@type": "http://www.w3.org/2001/XMLSchema#gYear", "@value": year}
    if date_raw and date_raw.strip():
        node["schema:temporal"] = date_raw.strip()

    if content_subjects:
        # id-only references; display names live in collection/labels.jsonld.json
        node["schema:about"] = [{"@id": c["@id"]} for c in content_subjects]

    return node, sidecars, (basenames[0] if basenames else None)


def main():
    manifest = load_manifest()
    items_made = []
    report = {"kept": [], "skipped_not_good": [], "good_no_masters": [], "masters_no_good_row": []}

    # ---- GROUPED -> multi-page items ----
    grouped_rows = read_rows(SRC / "grouped.csv")
    # group masters by subdir
    grouped_by_dir = {}
    for p in manifest["Grouped"]:
        sub = p.split("/")[1]  # Chicago_Cafe_Grouped_NNN
        grouped_by_dir.setdefault(sub, []).append(p)
    seen_dirs = set()
    for row in grouped_rows:
        abridged = row["Abridged File Name"].strip()      # grouped_001
        rec = (row.get("Recommendation") or "").strip()
        num = abridged.split("_")[-1]
        master_dir = f"Chicago_Cafe_Grouped_{num}"
        if rec != GOOD:
            report["skipped_not_good"].append((abridged, rec))
            continue
        tifs = sorted(grouped_by_dir.get(master_dir, []))
        if not tifs:
            report["good_no_masters"].append((abridged, "no master dir " + master_dir))
            continue
        seen_dirs.add(master_dir)
        title = (row.get("Title") or "").strip() or f"[Untitled] {abridged}"
        node, sidecars, _ = build_item(
            abridged, title, "multi", tifs,
            row.get("Date", ""), row.get("Description", ""),
            content_type_for(title), row.get("Box: Folder", ""))
        items_made.append((abridged, node, sidecars, tifs))
        report["kept"].append(abridged)
    for d in grouped_by_dir:
        if d not in seen_dirs:
            report["masters_no_good_row"].append(d)

    # ---- LOOSE -> single items (recto+verso) ----
    loose_rows = read_rows(SRC / "loose.csv", divider_text="Moved to Grouped")
    loose_by_num = {}
    for p in manifest["Loose"]:
        m = re.search(r"Loose_(\d+)_", p)
        if m:
            loose_by_num.setdefault(m.group(1), []).append(p)
    for row in loose_rows:
        abridged = row["Abridged File Name"].strip()       # loose_0001
        rec = (row.get("Recommendation") or "").strip()
        num = abridged.split("_")[-1]
        if rec != GOOD:
            report["skipped_not_good"].append((abridged, rec))
            continue
        tifs = sorted(loose_by_num.get(num, []))  # recto before verso (alpha)
        if not tifs:
            report["good_no_masters"].append((abridged, f"no Loose_{num}"))
            continue
        title = (row.get("Title") or "").strip() or f"[Untitled] {abridged}"
        node, sidecars, _ = build_item(
            abridged, title, "single", tifs,
            row.get("Date", ""), "",  # loose CSV has no Description column
            content_type_for(title), row.get("Box: Folder", ""))
        items_made.append((abridged, node, sidecars, tifs))
        report["kept"].append(abridged)

    # ---- PHOTOS -> single items (recto+verso) ----
    photos_rows = read_rows(SRC / "photos.csv")
    photos_by_num = {}
    for p in manifest["Photos"]:
        m = re.search(r"Photos_(\d+)_", p)
        if m:
            photos_by_num.setdefault(m.group(1), []).append(p)
    for row in photos_rows:
        abridged = row["Abridged File Name"].strip()       # photos_0001
        rec = (row.get("Recommendation") or "").strip()
        num = abridged.split("_")[-1]
        if rec != GOOD:
            report["skipped_not_good"].append((abridged, rec))
            continue
        tifs = sorted(photos_by_num.get(num, []))
        if not tifs:
            report["good_no_masters"].append((abridged, f"no Photos_{num}"))
            continue
        title = (row.get("Title") or "").strip() or f"[Untitled] {abridged}"
        node, sidecars, _ = build_item(
            abridged, title, "single", tifs,
            row.get("Date", ""), row.get("Description", ""),
            [CT_PHOTOGRAPHS], row.get("Box: Folder", ""))
        items_made.append((abridged, node, sidecars, tifs))
        report["kept"].append(abridged)

    # ---- Write item trees ----
    items_root = REPO / "items"
    for item_id, node, sidecars, tifs in items_made:
        write_json(items_root / f"{item_id}.jsonld.json", node)
        write_json(items_root / item_id / "media.jsonld.json", media_container())
        write_json(items_root / item_id / "media" / "images.jsonld.json", image_list_container())
        for dest, obj in sidecars:
            write_json(REPO / dest, obj)

    # ---- Collection node ----
    coll = {
        "@context": CONTEXT, "@id": "",
        "@type": ["schema:Collection", "http://fedora.info/definitions/v4/repository#ArchivalGroup"],
        "ucdlib:hasLabel": {"@id": "@base:/labels"},
        "schema:name": "Chicago Cafe Records",
        "schema:description": "TODO: collection-level description (Chicago Cafe, Woodland, CA — "
                              "menus, ephemera, and photographs from the Fong family's Chicago Cafe).",
        "schema:identifier": [COLLECTION_ID, "ark:/PLACEHOLDER/chicago-cafe"],
        "schema:license": {"@id": LICENSE},
        "schema:publisher": [PUBLISHER],
        "schema:about": [{"@id": c["@id"]} for c in (CT_PHOTOGRAPHS, CT_MENUS, CT_EPHEMERA)],
        "schema:sdLicense": {"@id": LICENSE},
        "schema:sdPublisher": [PUBLISHER],
    }
    write_json(REPO / "collection" / f"{COLLECTION_SLUG}.jsonld.json", coll)

    # initial labels from the content-type facet terms; apply_fast.py extends this
    # with every per-item FAST subject (id -> display name).
    labels = [{
        "@id": "", "@context": {"ucdlib": "http://digital.ucdavis.edu/schema#"},
        "@type": ["ucdlib:LabelService", "ucdlib:Service"],
    }] + [
        {"@id": c["@id"], "http://schema.org/name": c["schema:name"]}
        for c in (CT_PHOTOGRAPHS, CT_MENUS, CT_EPHEMERA)
    ]
    write_json(REPO / "collection" / COLLECTION_SLUG / "labels.jsonld.json", labels)

    # ---- Item index (for the FAST subject-proposal step) ----
    index = []
    for item_id, node, sidecars, tifs in items_made:
        index.append({
            "item_id": item_id,
            "type": "grouped" if item_id.startswith("grouped") else
                    ("photos" if item_id.startswith("photos") else "loose"),
            "title": node.get("schema:name", ""),
            "description": node.get("schema:description", ""),
            "date": node.get("schema:temporal", ""),
        })
    write_json(REPO / "fast" / "items_index.json", index)

    # ---- Coverage report ----
    n_multi = sum(1 for i in items_made if len(i[3]) > 2 or any("Grouped" in t for t in i[3]))
    lines = []
    lines.append(f"# Chicago Cafe (D-822) build coverage\n")
    lines.append(f"- Items generated: **{len(items_made)}**")
    g = sum(1 for i in items_made if i[0].startswith('grouped'))
    l = sum(1 for i in items_made if i[0].startswith('loose'))
    p = sum(1 for i in items_made if i[0].startswith('photos'))
    lines.append(f"  - grouped (multi-page): {g}")
    lines.append(f"  - loose (single): {l}")
    lines.append(f"  - photos (single): {p}")
    total_tifs = sum(len(i[3]) for i in items_made)
    lines.append(f"- TIFF images referenced: **{total_tifs}**")
    lines.append("")
    lines.append(f"## Good rows with NO master files ({len(report['good_no_masters'])}) — need attention")
    for a, why in report["good_no_masters"]:
        lines.append(f"- {a}: {why}")
    lines.append("")
    lines.append(f"## Master dirs/sets with no 'Good' CSV row ({len(report['masters_no_good_row'])})")
    for d in sorted(report["masters_no_good_row"]):
        lines.append(f"- {d}")
    lines.append("")
    lines.append(f"## Rows skipped (not 'Good for digital collection'): {len(report['skipped_not_good'])}")
    (REPO / "coverage_report.md").write_text("\n".join(lines), encoding="utf-8")

    print("\n".join(lines[:14]))
    print(f"\nWrote {len(items_made)} items. Full report: coverage_report.md")


if __name__ == "__main__":
    main()
