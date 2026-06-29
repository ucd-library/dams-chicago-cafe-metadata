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

### Still to confirm (human review)
- **Rights statement**: `InC-NC` assumed — confirm.
- **Collection description / creator**: placeholder text in `collection/chicago-cafe.jsonld.json`.
- **Loose recto/verso alignment**: the source notes a verso-numbering misalignment after
  `loose_0024`; verify those pairings against the physical items.
- 8 low-frequency subject phrases didn't resolve to FAST (logged by `apply_fast.py`).

## Import (on the digitization server)

```bash
fin io import --dry-run --ag-import-strategy version-all .
fin io import --ag-import-strategy version-all .
```
