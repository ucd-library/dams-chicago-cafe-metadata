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
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
MASTERS = Path("/digitization/Final_Output_Masters_Backup/Smaller_Requests/"
               "D-Collections/D-822_Chicago_Cafe_Records")


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
    sidecars = glob.glob(str(REPO / "items" / "*" / "media" / "images" / "*.tif.jsonld.json"))
    linked = missing = 0
    missing_list = []
    for sc in sidecars:
        basename = os.path.basename(sc)[:-len(".jsonld.json")]  # X.tif
        dest = Path(sc).parent / basename
        src = master_for(basename)
        if not src or not src.exists():
            missing += 1
            missing_list.append(basename)
            continue
        if dry:
            linked += 1
            continue
        if dest.is_symlink() or dest.exists():
            dest.unlink()
        os.symlink(src, dest)
        linked += 1
    print(f"sidecars: {len(sidecars)}; {'would link' if dry else 'linked'}: {linked}; missing masters: {missing}")
    if missing_list:
        print("MISSING:")
        for m in missing_list[:50]:
            print("  ", m)


if __name__ == "__main__":
    main()
