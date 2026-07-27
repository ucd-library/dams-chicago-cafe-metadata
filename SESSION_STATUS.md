# Chicago Cafe (D-822) — session status

Dev DAMS: https://dev.dams.library.ucdavis.edu/ · Collection ARK `ark:/87293/d30c4sv8b`
GitHub: `ucd-library/dams-chicago-cafe-metadata` (metadata only)

## Done
- **373 items** imported to dev (103 grouped multi-page, 90 loose, 180 photos), real EZID ARKs, FAST subjects, content-type facet (Photographs/Menus/Ephemera). Derivatives generated.
- **Orientation fixed** (pixels baked, masters untouched): `grouped_088` (1949 calendar), `grouped_089` left as-is, `grouped_015` (order pads), `grouped_115` (1988 calendar).
- **46 three-page menus split** into clean 4-page bifolds (cover / inside-left / inside-right / back), re-imported, derivatives regenerated. Confirmed displaying as books.
- Review JPEGs/PDFs of the split menus: `/Users/jmpike/pictures/Chicago_Cafe_3page_menus_review/`.

## Outstanding (DAMS-side, data is correct)
1. **Subject labels — RESOLVED 2026-07-06.** Root cause: the label store only ingests a collection's labels container on certain events, and D-822's never got ingested; Dusty fixed the ingest side. Fix applied: `fin reindex start /collection/ark:/87293/d30c4sv8b/labels`, then a collection reindex with `-f hasPart`. Verified: **all 373 items fully resolved** (0 partial) via API sweep.
2. **Book viewer** — two-up view shows a neighbor-page peek; pure viewer behavior. Optional polish (IIIF `viewingHint: paged`).

## AI-metadata sibling collection (2026-07-06)
Parallel collection "Chicago Cafe Records (AI-generated metadata)" (`ark:/87293/zzai0coll`, `D-822-AI`) built and importing — see `~/dams-chicago-cafe-ai-metadata/SESSION_STATUS.md`.

### Paste to Dusty (updated 2026-07-06 with root-cause evidence)
> D-822 Chicago Cafe Records (`ark:/87293/d30c4sv8b`) — FAST subject labels: I can now show exactly what's wrong. The collection uses 104 distinct FAST ids; only **10 resolve to names** in the indexed item records, and those 10 are **exactly** the ids that also appear in some *other* collection's `/labels` container (Menus+Photographs+Ephemera ← Long, Portrait photography ← Riley, Women/California/Nevada ← Mundell, Cooking Chinese ← Yan, Sacramento ← Postcards, SF ← Beckstoffer). Perfect 10/10 match, zero exceptions. So label resolution clearly reads from a global label store fed by collections' labels containers — and D-822's labels container (all 104 mappings present in fcrepo, publicly readable at `/fcrepo/rest/collection/ark:/87293/d30c4sv8b/labels`) was **never ingested into that store**. Reindexing the labels container (`fin reindex start`) didn't do it — its ES doc is just `@id`+`lastModified`, same as every other collection's, so that's not the path. What triggers label-store ingestion for a collection's LabelService, and can you kick it for D-822?

Verified 2026-07-06: labels container in fcrepo has all 104 id→name mappings; item ES records unchanged since 6/29; resolved set == (our ids ∩ union of all other collections' labels containers).

## Operational notes (for next collection)
- **CLI:** the modern fin CLI is **`@ucd-lib/fin-api`** (v2.1.0), NOT the stale public `@ucd-lib/fin-cli` (0.12.3, wrong `.ttl`/`.fin` serialization). Installed globally on the digitization server (Node via nvm). Reach the server by IP `169.237.102.147` if Tailscale name `digitization` is down.
- **Import:** `fin io import --ag-import-strategy version-all .` from repo root. It re-hashes the ENTIRE collection (no path filter in 2.1.0), so for a small fix build a tiny tree of just the changed items (symlinks, on `/digitization` not `/tmp` which is small) and import that.
- **Derivatives:** the `image-products` workflow must be started on each **binary path** (`/item/ark:/.../media/images/X.tif`), not the item or collection (those stay `pending` forever). `--force` to regenerate. A collection reindex with `hasPart` crawl auto-triggers them.
- **Orientation:** `dams-image-utils` does NOT auto-apply the TIFF orientation tag; bake rotation into pixels (PIL `ImageOps.exif_transpose`, verify with a thumbnail).
- Scripts in this repo: `build_collection.py`, `fast_lookup.py`, `apply_fast.py`, `mint_arks.py`, `stage_binaries.py`.
