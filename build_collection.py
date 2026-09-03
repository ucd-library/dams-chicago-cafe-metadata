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

# ---- Special cases from Kevin Miller's Aug 2026 review (Column H of the sheet) ----
# loose_0001 + loose_0068 are two halves of one early bifold menu, physically
# separated before digitization. Combined into a single Book under loose_0068
# (its metadata + ARK). Page order per Kevin's screenshot, verified against the
# scans: cover (0068 recto), American Bill of Fare (0068 verso), China Dishes
# (0001 VERSO), Eagle Dairy back-page ads (0001 RECTO).
COMBINE_INTO_LOOSE_0068 = [
    "Chicago_Cafe_Loose/Chicago_Cafe_Loose_0068_recto.tif",
    "Chicago_Cafe_Loose/Chicago_Cafe_Loose_0068_verso.tif",
    "Chicago_Cafe_Loose/Chicago_Cafe_Loose_0001_verso.tif",
    "Chicago_Cafe_Loose/Chicago_Cafe_Loose_0001_recto.tif",
]
COMBINE_SKIP = {"loose_0001"}  # absorbed into loose_0068

# photos_0113 ("Portrait of a young man"): both 0113 scans are the EMPTY mount
# card — the portrait itself was scanned as the Photos_0112 pair (excluded from
# the collection as its own item). Portrait first, mount kept as trailing pages.
PHOTOS_0113_PAGES = [
    "Chicago_Cafe_Photos/Chicago_Cafe_Photos_0112_recto.tif",
    "Chicago_Cafe_Photos/Chicago_Cafe_Photos_0112_verso.tif",
    "Chicago_Cafe_Photos/Chicago_Cafe_Photos_0113_recto.tif",
    "Chicago_Cafe_Photos/Chicago_Cafe_Photos_0113_verso.tif",
]

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

# Per-item content-type facet overrides (Kevin, Aug 2026): letters/cards filed
# with the photos are Ephemera, not Photographs.
FACET_OVERRIDES = {
    "photos_0060": [CT_EPHEMERA],
    "photos_0212": [CT_EPHEMERA],
    "photos_0187": [CT_EPHEMERA],  # 1953 PRC banknote (Kevin, 2026-08-28)
}

# EDTF (LOC level 0/1) dates for "Undated" items whose range/circa info lives in
# the Description column — the deferred pass, enabled by DAMS fuzzy-date support
# (ucd-library/dams#152, merged 2026-09-02). Emitted as plain-string
# schema:datePublished; the item transform parses EDTF and falls back to the
# first 4-digit year on older clients. Review sheet: drafts/edtf-dates.csv.
# "After 1997" items use 1997/2025 (the cafe closed in 2025).
EDTF_DATES = {
    'grouped_020': '1956/1968',
    'grouped_022': '2010~',
    'grouped_023': '1997/2010',
    'grouped_024': '1997/2010',
    'grouped_029': '2005/2010',
    'grouped_030': '2005/2010',
    'grouped_031': '1997/2010',
    'grouped_032': '1997/2010',
    'grouped_033': '1997/2010',
    'grouped_034': '2010/2015',
    'grouped_035': '2010/2015',
    'grouped_036': '2010/2015',
    'grouped_037': '1956/1968',
    'grouped_039': '195X',
    'grouped_041': '195X',
    'grouped_043': '195X',
    'grouped_044': '195X',
    'grouped_045': '1956/1968',
    'grouped_046': '1956/1968',
    'grouped_050': '2020/2025',
    'grouped_053': '1968/1997',
    'grouped_057': '1997/2025',
    'grouped_058': '1968/1997',
    'grouped_059': '1997/2025',
    'grouped_060': '1997/2025',
    'grouped_065': '199X',
    'grouped_067': '1968/1997',
    'grouped_070': '1965~',
    'grouped_071': '1968/1997',
    'grouped_072': '1997/2025',
    'grouped_074': '1968/1997',
    'grouped_075': '1997/2025',
    'grouped_078': '1968/1997',
    'grouped_079': '1968/1997',
    'grouped_082': '1989~',
    'grouped_083': '1968/1997',
    'grouped_086': '1968/1997',
    'grouped_092': '1997/2010',
    'grouped_093': '2020/2025',
    'grouped_097': '1963~',
    'grouped_098': '1963~',
    'grouped_100': '1963~',
    'grouped_118': '1920/1949',
    'grouped_123': '1953/1955',
    'loose_0003': '1920/1949',
    'loose_0068': '1920/1949',
    'loose_0080': '1959?',
    'loose_0094': '1920/1949',
    'loose_0114': '1953/1955',
    'loose_0115': '1953/1955',
    'loose_0116': '1953/1955',
    'photos_0006': '194X',
    'photos_0013': '195X',
    'photos_0015': '1935~',
    'photos_0018': '1935~',
    'photos_0019': '194X',
    'photos_0022': '196X',
    'photos_0024': '196X',
    'photos_0025': '196X',
    'photos_0028': '196X',
    'photos_0029': '196X',
    'photos_0031': '196X',
    'photos_0032': '196X',
    'photos_0033': '196X',
    'photos_0038': '196X',
    'photos_0040': '196X',
    'photos_0050': '195X',
    'photos_0051': '195X',
    'photos_0053': '195X',
    'photos_0054': '195X',
    'photos_0055': '195X',
    'photos_0059': '195X',
    'photos_0069': '1950/1969',
    'photos_0071': '1957~',
    'photos_0074': '196X',
    'photos_0075': '1950/1969',
    'photos_0076': '1950/1969',
    'photos_0081': '1948~',
    'photos_0082': '1948~',
    'photos_0083': '1948~',
    'photos_0085': '1950/1969',
    'photos_0086': '195X',
    'photos_0087': '1949~',
    'photos_0088': '1950/1969',
    'photos_0089': '1950/1969',
    'photos_0093': '196X',
    'photos_0120': '1950/1969',
    'photos_0121': '195X',
    'photos_0122': '195X',
    'photos_0123': '195X',
    'photos_0124': '195X',
    'photos_0132': '1950/1969',
    'photos_0148': '195X',
    'photos_0149': '195X',
    'photos_0151': '195X',
    'photos_0153': '195X',
    'photos_0154': '195X',
    'photos_0155': '195X',
    'photos_0156': '195X',
    'photos_0157': '195X',
    'photos_0158': '195X',
    'photos_0159': '195X',
    'photos_0160': '195X',
    'photos_0161': '195X',
    'photos_0162': '195X',
    'photos_0163': '195X',
    'photos_0166': '195X',
    'photos_0167': '195X',
    'photos_0168': '195X',
    'photos_0169': '195X',
    'photos_0171': '195X',
    'photos_0172': '195X',
    'photos_0173': '195X',
    'photos_0174': '195X',
    'photos_0175': '195X',
    'photos_0176': '195X',
    'photos_0178': '1950/1969',
    'photos_0179': '1950/1969',
    'photos_0180': '1950/1969',
    'photos_0183': '1950/1969',
    'photos_0184': '1950/1969',
    'photos_0189': '195X',
    'photos_0190': '195X',
    'photos_0191': '195X',
    'photos_0192': '195X',
    'photos_0193': '195X',
    'photos_0194': '195X',
    'photos_0195': '195X',
    'photos_0196': '195X',
    'photos_0198': '195X',
    'photos_0199': '195X',
    'photos_0202': '195X',
    'photos_0203': '195X',
    'photos_0204': '195X',
    'photos_0205': '195X',
    'photos_0208': '195X',
    'photos_0209': '195X',
    'photos_0210': '195X',
    'photos_0211': '195X',
    'photos_0212': '195X',
    'photos_0213': '195X',
    'photos_0214': '195X',
    'photos_0216': '195X',
    'photos_0217': '195X',
    'photos_0219': '195X',
    'grouped_120': '1920/1949',
    'photos_0017': '194X',
    'photos_0215': '194X',
}

# Items whose description gives an explicit likely span around a circa year
# ("Circa 1963, and likely between 1959 and 1968"): ±N year search widening.
EDTF_UNCERTAINTY_YEARS = {
    "grouped_097": 5,
    "grouped_098": 5,
    "grouped_100": 5,
}


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

XSD = "http://www.w3.org/2001/XMLSchema#"


def extract_year(*texts):
    """Return first plausible 4-digit year found, else None."""
    for t in texts:
        if not t:
            continue
        m = YEAR_RE.search(t)
        if m:
            return m.group(1)
    return None


def parse_date(date_raw):
    """Parse the CSV Date column into (xsd_datatype, value) for schema:datePublished.

    Full dates from the spreadsheet must display in full (Kevin's "Full date?"
    correction round, Aug 2026):
      MM-DD-YYYY / M/D/YYYY -> xsd:date  YYYY-MM-DD
      MM-YYYY (also "05- 1961") -> xsd:gYearMonth  YYYY-MM
      YYYY -> xsd:gYear
      "Undated" / blank -> (None, None)  (range/circa text lives in Description)
      decades & ranges ("1980s", "1920s - 1940s") -> first year as xsd:gYear —
        interim until the DAMS imprecise-date support lands; raw string is
        preserved in schema:temporal either way.
    """
    d = (date_raw or "").strip()
    if not d or d.lower() == "undated":
        return None, None
    m = re.fullmatch(r"(\d{1,2})\s*[-/]\s*(\d{1,2})\s*[-/]\s*(\d{4})", d)
    if m:
        mo, dy, yr = int(m.group(1)), int(m.group(2)), m.group(3)
        return XSD + "date", f"{yr}-{mo:02d}-{dy:02d}"
    m = re.fullmatch(r"(\d{1,2})\s*[-/]\s*(\d{4})", d)
    if m:
        return XSD + "gYearMonth", f"{m.group(2)}-{int(m.group(1)):02d}"
    if re.fullmatch(r"\d{4}", d):
        return XSD + "gYear", d
    m = re.fullmatch(r"(\d{3})0s\s*[-\u2013]\s*(\d{3})0s", d)
    if m:  # "1920s - 1940s" -> EDTF interval 1920/1949 (edtf.js L1 rejects masked interval endpoints like 192X/194X)
        return "EDTF", f"{m.group(1)}0/{m.group(2)}9"
    m = re.fullmatch(r"(\d{3})0s", d)
    if m:  # "1980s" -> EDTF decade
        return "EDTF", f"{m.group(1)}X"
    year = extract_year(d)
    if year:
        return XSD + "gYear", year
    return None, None


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

    dtype, dval = parse_date(date_raw)
    if item_id in EDTF_DATES:
        dtype, dval = "EDTF", EDTF_DATES[item_id]
    if dval:
        # EDTF expressions ("192X/194X") are not valid XSD values — plain string
        node["schema:datePublished"] = (dval if dtype == "EDTF"
                                        else {"@type": dtype, "@value": dval})
    if item_id in EDTF_UNCERTAINTY_YEARS:
        node["ucdlib:dateUncertaintyYears"] = EDTF_UNCERTAINTY_YEARS[item_id]
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
        if abridged in COMBINE_SKIP:
            report["skipped_not_good"].append((abridged, "combined into loose_0068"))
            continue
        if rec != GOOD:
            report["skipped_not_good"].append((abridged, rec))
            continue
        if abridged == "loose_0068":
            tifs = COMBINE_INTO_LOOSE_0068
            item_type = "multi"  # 4-page bifold -> Book
        else:
            tifs = sorted(loose_by_num.get(num, []))  # recto before verso (alpha)
            item_type = "single"
        if not tifs:
            report["good_no_masters"].append((abridged, f"no Loose_{num}"))
            continue
        title = (row.get("Title") or "").strip() or f"[Untitled] {abridged}"
        node, sidecars, _ = build_item(
            abridged, title, item_type, tifs,
            row.get("Date", ""), row.get("Description", ""),
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
        if abridged == "photos_0113":
            tifs = PHOTOS_0113_PAGES  # portrait was scanned as the 0112 pair
        else:
            tifs = sorted(photos_by_num.get(num, []))
        if not tifs:
            report["good_no_masters"].append((abridged, f"no Photos_{num}"))
            continue
        title = (row.get("Title") or "").strip() or f"[Untitled] {abridged}"
        node, sidecars, _ = build_item(
            abridged, title, "single", tifs,
            row.get("Date", ""), row.get("Description", ""),
            FACET_OVERRIDES.get(abridged, [CT_PHOTOGRAPHS]), row.get("Box: Folder", ""))
        items_made.append((abridged, node, sidecars, tifs))
        report["kept"].append(abridged)

    # ---- Write item trees ----
    items_root = REPO / "items"
    for item_id, node, sidecars, tifs in items_made:
        write_json(items_root / f"{item_id}.jsonld.json", node)
        write_json(items_root / item_id / "media.jsonld.json", media_container())
        write_json(items_root / item_id / "media" / "images.jsonld.json", image_list_container())
        for dest, obj in sidecars:
            # Preserve Title II alt text (digtk alt run writes it onto these
            # sidecars); a rebuild must never drop it.
            existing = REPO / dest
            if existing.exists():
                try:
                    alt = json.loads(existing.read_text()).get("schema:alternativeHeadline")
                except (ValueError, OSError):
                    alt = None
                if alt and "schema:alternativeHeadline" not in obj:
                    obj["schema:alternativeHeadline"] = alt
            write_json(REPO / dest, obj)

    # ---- Collection node ----
    # The collection node is hand-maintained (Fong-family description, curated
    # top-10 FAST subjects, real ARK) — never overwrite an existing one.
    coll_path = REPO / "collection" / f"{COLLECTION_SLUG}.jsonld.json"
    if coll_path.exists():
        print("collection node exists — left untouched (hand-maintained)")
        coll = None
    else:
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
    if coll is not None:
        write_json(coll_path, coll)

    # initial labels from the content-type facet terms; apply_fast.py extends this
    # with every per-item FAST subject (id -> display name). Same guard: don't
    # clobber the full label set apply_fast.py maintains.
    labels_path = REPO / "collection" / COLLECTION_SLUG / "labels.jsonld.json"
    if not labels_path.exists():
        labels = [{
            "@id": "", "@context": {"ucdlib": "http://digital.ucdavis.edu/schema#"},
            "@type": ["ucdlib:LabelService", "ucdlib:Service"],
        }] + [
            {"@id": c["@id"], "http://schema.org/name": c["schema:name"]}
            for c in (CT_PHOTOGRAPHS, CT_MENUS, CT_EPHEMERA)
        ]
        write_json(labels_path, labels)

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
