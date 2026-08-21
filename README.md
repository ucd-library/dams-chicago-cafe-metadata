# dams-chicago-cafe-metadata

D-822 — Chicago Cafe Records. Fin-filesystem serialization for import into the UC Davis
Library DAMS via `fin io import`. First pass uses **human-generated** metadata (from the
archivist's "digitized file analysis" spreadsheets).

## What's here

```
collection/chicago-cafe.jsonld.json     # schema:Collection + fedora:ArchivalGroup
collection/chicago-cafe/labels.jsonld.json
items/<id>.jsonld.json                   # one node per item
items/<id>/media/...                      # media + per-image sidecars
build_collection.py                      # regenerates the tree from source_csv/
source_csv/                              # the 3 analysis CSVs + masters_manifest.txt
coverage_report.md                       # what was included/excluded and why
```

Item id ↔ source mapping:
- `grouped_NNN` → multi-page item (`schema:Book`), pages from `Chicago_Cafe_Grouped_NNN/`.
- `loose_NNNN` → single item (`schema:ImageObject`), recto+verso.
- `photos_NNNN` → single item (`schema:ImageObject`), recto+verso.

Only rows marked **"Good for digital collection"** are included (373 items, 1209 images).

## Binaries (TIFF masters)

Not tracked in git. Masters live (read-only) at:
`/digitization/Final_Output_Masters_Backup/Smaller_Requests/D-Collections/D-822_Chicago_Cafe_Records`
on the digitization server. Before import, copy each item's TIFFs into its
`items/<id>/media/images/` directory (filenames already referenced by the sidecars).

## Regenerate

```bash
python3 build_collection.py
```

## Status

- **ARKs**: ✅ minted via EZID (shoulder `ark:/87293/d3`). Collection = `ark:/87293/d30c4sv8b`.
  Mapping in `arks/ark_map.json`. `mint_arks.py` is idempotent (won't re-mint).
- **FAST subjects**: ✅ content-type facet (Photographs / Menus / Ephemera) with real FAST
  ids, plus per-item topical/geographic FAST subjects (104 distinct terms, authorized
  against the live OCLC FAST API). Regenerate via `apply_fast.py`.
- **Kevin Miller's review applied (2026-08)**: source CSVs refreshed from his reviewed
  Google Sheet (Column H = correction checklist). 371 items now:
  - `loose_0001` combined into `loose_0068` (one 4-page bifold Book, 0068's ARK);
    `loose_0067` dropped. Both need explicit DAMS-side DELETEs.
  - `photos_0113`: portrait pages (`Photos_0112_*`) added before the empty mount scans.
  - Full dates now emit `xsd:date` / `gYearMonth` (Kevin's "Full date?" fix);
    "Undated" emits no `datePublished`; decades/ranges keep first-year `gYear`
    until DAMS imprecise-date support lands.
  - Facet overrides: `photos_0060`, `photos_0212` → Ephemera; `grouped_087` retitled
    (was "1:8") + Woodland/Chinese-restaurants subjects.
  - Collection node & labels are hand-maintained — `build_collection.py` no longer
    overwrites them.

### ⚠️ Import safety
NEVER run a full-tree binary import: masters still hold the pre-split 3-page menus, and
fin's SHA compare would overwrite the 46 split bifolds. Metadata = slim tree (no images);
binaries only via targeted per-item trees.

### Still to confirm (human review)
- **Rights statement**: `InC-NC` assumed — confirm.
- 8 low-frequency subject phrases didn't resolve to FAST (logged by `apply_fast.py`).
- Alt-text from (shortened) AI descriptions — future round, per email with Kevin.

## Import (on the digitization server)

```bash
fin io import --dry-run --ag-import-strategy version-all .
fin io import --ag-import-strategy version-all .
```
