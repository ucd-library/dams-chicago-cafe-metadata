# Chicago Cafe (D-822) — and the general DAMS collection-build playbook

This repo built the "Chicago Cafe Records" collection on dev DAMS
(`ark:/87293/d30c4sv8b`). The pipeline here is the template for future collections.

## The pipeline (in order)
1. **Source data**: archivist's review spreadsheet → CSVs in `source_csv/`. Only rows
   marked "Good for digital collection" are built. Correction rounds arrive as new CSV
   exports (here: Column H "Digital Collection (human)" = the correction checklist).
2. **`build_collection.py`** — emits the fin-filesystem tree (`collection/` + `items/`),
   placeholder ARKs. Idempotent; special cases (combined items, page-order fixes, facet
   overrides) are config blocks at the top. It never overwrites the hand-maintained
   collection node/labels, and never deletes files — remove dropped items with `git rm`.
3. **`mint_arks.py`** — mints real EZID ARKs (`ark:/87293/d3` shoulder), records them in
   `arks/ark_map.json`, substitutes into the tree. Idempotent, never double-mints.
   Re-run after every rebuild (rebuilds regress to placeholders).
4. **`apply_fast.py`** — merges FAST subjects from `fast/proposals/*.json` (id-only refs
   on items; names in `collection/<slug>/labels.jsonld.json`). Offline-safe via
   `fast_cache.json`. Manual subject additions = drop a small proposals file in.
5. **`stage_binaries.py`** — ON the server: symlinks master TIFFs next to their sidecars
   (resolves by basename, so cross-item pages like a combined menu's work).
6. **Import** — see below.

## Import rules (hard-won)
- CLI is **`@ucd-lib/fin-api` 2.1.0** (`fin`), NOT the stale `fin-cli`.
- Auth: `fin auth login` works on the Mac; on the server the redirect is unusable —
  `scp ~/.fccli jmpike@digitization:` (token ~24h).
- **Metadata changes: slim tree only** (`collection/` + `items/*.jsonld.json` node files,
  zero binaries). ~45s for the whole collection; fin does NOT treat absent media as
  deletions. Always `--dry-run` first and grep for DELETE.
- **Metadata imports run fine from the Mac.** Binary imports do NOT — Cloudflare kills
  PUTs at ~100s and our uplink can't push 50-90MB TIFFs that fast (524s). Run binary
  imports from the digitization server (symlinked masters, seconds per file).
- **NEVER full-tree binary import for this collection**: masters still hold the pre-split
  3-page menus; fin's SHA compare would clobber the 46 split bifolds.
- Import command: `fin io import --ag-import-strategy version-all .`
- Deleting items: `fin http delete -p /item/ark:/...` (permanent, clears tombstone).
  fin import never deletes — DAMS-side removal is always an explicit step.

## After import
- `image-products` auto-triggers per new binary. Check: `fin workflow get <binary path>`.
  Rerun: `fin workflow start -f <path> image-products`; nuclear: `fin workflow delete`
  then `start` (regenerates all products for that binary).
- Reindex: `fin reindex start -f hasPart /collection/ark:/...` (also fixes label
  resolution — labels container must be ingested into the global label store).
- The client-side collection edits (thumbnail `featuredImage.jpg`, Highlights, watercolor
  css) live under `/application/ucd-lib-client/...` — imports never touch them.
- Item-count updates come via reindex; ES docs for DELETED items may linger (open issue
  with Dusty as of 2026-08-21, see SESSION_STATUS.md).

## Dates
`schema:datePublished` gets the most precise XSD type the source allows (`xsd:date`,
`gYearMonth`, `gYear` — see `parse_date`); raw string preserved in `schema:temporal`;
"Undated" emits no datePublished. When DAMS ships EDTF (LOC level 0/1: `1956/1968`,
`196X`, `1962~`, `1962?`), do the deferred pass over the ~90 "Undated" items whose
range/circa info sits in their descriptions.

## Current status
See `SESSION_STATUS.md` (kept current; includes outstanding DAMS-side issues and the
draft email to Kevin in `drafts/`).
