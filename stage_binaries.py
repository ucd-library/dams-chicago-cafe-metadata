#!/usr/bin/env python3
"""
Stage the master TIFFs into the collection tree for `fin io import`.

Runs ON the digitization server. For every per-image sidecar
(items/<id>/media/images/<basename>.tif.jsonld.json) it creates a SYMLINK
<basename>.tif next to the sidecar, pointing at the read-only master. Symlinks
are instant and add no disk (the 68 GB is never duplicated); fin reads the file
bytes through the link. Masters are READ-ONLY and never modified.

Verifies every referenced master exists; reports any missing.
"""
import glob
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
MASTERS = Path("/digitization/Final_Output_Masters_Backup/Smaller_Requests/"
               "D-Collections/D-822_Chicago_Cafe_Records")

# Renamed tree (Sept 2026): sidecars carry NEW names (D-822_...); masters keep
# scan-time names. new basename -> old basename via arks/file_rename_map.json.
try:
    _fm = json.loads((REPO / "arks" / "file_rename_map.json").read_text())
    NEW_TO_OLD = {v: k for k, v in _fm.items()}
except FileNotFoundError:
    NEW_TO_OLD = {}

# For the 46 split bifolds the masters hold PRE-SPLIT pixels under the same old
# names — their pages MUST come from the split trees, searched before masters.
# Pass one or more --extra <dir> (e.g. /digitization/cc_menus, the server human
# checkout) ; every dir is indexed recursively by old basename.
EXTRA_INDEX = {}
SPLIT_ITEMS = set()
try:
    SPLIT_ITEMS = set(json.loads((REPO / "arks" / "page_overrides.json").read_text()))
except FileNotFoundError:
    pass


def index_extra(dirs):
    for d in dirs:
        for root, _dirs, files in os.walk(d, followlinks=True):
            for f in files:
                if f.endswith(".tif") and f not in EXTRA_INDEX:
                    EXTRA_INDEX[f] = Path(root) / f


def master_for(basename):
    if basename.startswith("Chicago_Cafe_Grouped_"):
        m = re.match(r"(Chicago_Cafe_Grouped_\d+)_", basename)
        return MASTERS / "Chicago_Cafe_Grouped" / m.group(1) / basename
    if basename.startswith("Chicago_Cafe_Loose_"):
        return MASTERS / "Chicago_Cafe_Loose" / basename
    if basename.startswith("Chicago_Cafe_Photos_"):
        return MASTERS / "Chicago_Cafe_Photos" / basename
    return None


def main():
    dry = "--dry-run" in sys.argv
    args = sys.argv[1:]
    extra_dirs = [args[i + 1] for i, a in enumerate(args) if a == "--extra"]
    pdf_dirs = [args[i + 1] for i, a in enumerate(args) if a == "--pdfs"]
    if extra_dirs:
        index_extra(extra_dirs)
    sidecars = glob.glob(str(REPO / "items" / "*" / "media" / "images" / "*.tif.jsonld.json"))
    linked = missing = 0
    missing_list = []
    split_from_masters = []
    for sc in sidecars:
        basename = os.path.basename(sc)[:-len(".jsonld.json")]  # X.tif (new name)
        item_id = Path(sc).parents[2].name
        old_basename = NEW_TO_OLD.get(basename, basename)
        dest = Path(sc).parent / basename
        src = EXTRA_INDEX.get(old_basename) or master_for(old_basename)
        if src and src.exists() and item_id in SPLIT_ITEMS and old_basename not in EXTRA_INDEX:
            # a bifold page about to be linked from MASTERS = pre-split pixels
            split_from_masters.append(basename)
        if not src or not src.exists():
            missing += 1
            missing_list.append(f"{basename} (master name {old_basename})")
            continue
        if dry:
            linked += 1
            continue
        if dest.is_symlink() or dest.exists():
            dest.unlink()
        os.symlink(src, dest)
        linked += 1
    # ---- Attached PDFs: items/<id>/media/<name>.pdf.jsonld.json <- <pdfdir>/<item_id>.pdf
    pdf_linked = pdf_missing = 0
    for psc in glob.glob(str(REPO / "items" / "*" / "media" / "*.pdf.jsonld.json")):
        pdf_name = os.path.basename(psc)[:-len(".jsonld.json")]
        item_id = Path(psc).parents[1].name
        src = next((Path(d) / f"{item_id}.pdf" for d in pdf_dirs if (Path(d) / f"{item_id}.pdf").exists()), None)
        dest = Path(psc).parent / pdf_name
        if src is None:
            pdf_missing += 1
            continue
        if not dry:
            if dest.is_symlink() or dest.exists():
                dest.unlink()
            os.symlink(src, dest)
        pdf_linked += 1

    print(f"sidecars: {len(sidecars)}; {'would link' if dry else 'linked'}: {linked}; missing masters: {missing}")
    print(f"pdfs: {'would link' if dry else 'linked'} {pdf_linked}; missing: {pdf_missing}"
          + ("" if pdf_dirs else "  (no --pdfs dir given)"))
    if split_from_masters:
        print(f"FATAL: {len(split_from_masters)} split-bifold pages would come from PRE-SPLIT "
              "masters — pass --extra <split-tree-dir> (e.g. /digitization/cc_menus). First few:")
        for b in split_from_masters[:8]:
            print("  ", b)
        sys.exit(1)
    if missing_list:
        print("MISSING:")
        for m in missing_list[:50]:
            print("  ", m)


if __name__ == "__main__":
    main()
