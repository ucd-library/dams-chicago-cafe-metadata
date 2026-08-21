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

## Kevin Miller review round (2026-08-21)
Parsed from `Re: Digital Collections CSV Template.pdf` (email thread) + the reviewed
Google Sheet CSVs (Column H "Digital Collection (human)" = checklist; tan/older columns
ignored). Rebuilt the tree — 371 items (was 373). All metadata edits are in this commit;
**not yet imported to dev**.

Import runbook (server, from the repo checkout):
1. Pull this commit; `python3 stage_binaries.py --dry-run` NOT needed for metadata.
2. Metadata slim tree (per metadata-only rule): `collection/` + all `items/*.jsonld.json`
   node files, no `media/` binaries → `fin io import --dry-run` first, grep DELETE.
3. Binary trees (only two): `items/loose_0068/` (4 tifs — 2 new Loose_0001 pages, order
   cover/AmBillOfFare/ChinaDishes[=0001_verso]/backAds[=0001_recto]) and
   `items/photos_0113/` (4 tifs — 2 new Photos_0112 pages first). Include media/ +
   sidecars (existing pages get new positions). Symlink masters via stage_binaries logic.
4. DAMS deletes (fin/HTTP DELETE + tombstone): loose_0001 `ark:/87293/d3wd3qb7b`,
   loose_0067 `ark:/87293/d3p55ds8d`.
5. Verify: image-products auto-run on the 4 new binaries; loose_0068 renders as Book with
   4 pages; photos_0113 thumbnail = portrait; photos_0001-style full dates display
   (e.g. grouped_121 → 1945-12-11); item count 371.
6. Kevin's admin edits (thumbnail featuredImage.jpg + 6 highlights) live in
   `/application/ucd-lib-client/...` — imports don't touch them; confirm still present,
   then email Kevin for his final pass.

Notes: dates — full dates now xsd:date/gYearMonth; "Undated" per Kevin displays via
temporal only; decades/ranges keep first-year gYear until Dusty's imprecise-date fix.
Collection description: worldcat markdown links replaced with plain text (Kevin: links
didn't work). grouped_001 page order verified already correct on dev (stale note).

### Paste to Dusty (2026-08-21, two dev issues after Kevin-review import)
> D-822 Chicago Cafe (`ark:/87293/d30c4sv8b`), two dev issues after today's update:
> 1. **image-products won't produce small.jpg for 2 binaries** — `/item/ark:/87293/d3j09wf3v/media/images/Chicago_Cafe_Photos_0112_recto.tif` and `/item/ark:/87293/d33t9dh36/media/images/Chicago_Cafe_Loose_0001_verso.tif`. Three runs each (auto on import, `start -f`, and `workflow delete` + fresh start — last one regenerated medium/large/tiled/ocr from scratch) all end gcExecution SUCCEEDED, but GCS 404s the small: `{"error":"No such object: dams-client-media-prod/item/.../images/small.jpg"}` while medium/large/tiled/ocr all serve 200. The indexed clientMedia record *claims* a 256px small exists. Sibling scans from the same batch (e.g. `..._0112_verso.tif`) are fine. Last clean-slate workflow: `bf4e45c3-7a8a-411b-9668-dcaabbedad92` (image-products-dev, dams-image-utils 2.8.4). Can you check what the small.jpg step actually did in that execution?
> 2. **Deleted items linger in ES** — I permanently deleted `/item/ark:/87293/d3wd3qb7b` and `/item/ark:/87293/d3p55ds8d` (404 in fcrepo, tombstones purged), and itemCount correctly dropped to 371, but `/api/item/...` still returns their old records and they still surface in search. A collection reindex (`-f hasPart`) didn't purge them (status has also been stuck on "started" for a while). What's the right way to remove ES docs for deleted resources?
