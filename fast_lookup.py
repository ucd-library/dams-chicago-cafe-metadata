#!/usr/bin/env python3
"""
Resolve free-text subject phrases to authoritative OCLC FAST headings.

Uses the public, key-free fast.oclc.org searchfast suggest API. Never invents
FAST ids — only returns headings the authority actually contains. Results are
cached in fast_cache.json so re-runs are fast and deterministic.

  from fast_lookup import resolve
  resolve("Chinese restaurants")  -> {"@id": "http://id.worldcat.org/fast/...", "schema:name": "..."}  or None
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

CACHE_PATH = Path(__file__).resolve().parent / "fast_cache.json"
API = "https://fast.oclc.org/searchfast/fastsuggest"


def _load_cache():
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text())
    return {}


def _save_cache(cache):
    CACHE_PATH.write_text(json.dumps(cache, indent=2, ensure_ascii=False))


def _fast_url(idroot):
    # "fst01095907" -> "http://id.worldcat.org/fast/1095907"
    num = idroot.lower().replace("fst", "").lstrip("0") or "0"
    return f"http://id.worldcat.org/fast/{num}"


def _query(phrase, rows=10):
    params = urllib.parse.urlencode({
        "query": phrase,
        "queryIndex": "suggestall",
        "queryReturn": "suggestall,idroot,auth,type",
        "suggest": "autoSubject",
        "rows": rows,
    })
    url = f"{API}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "ucd-dams-chicago-cafe/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def resolve(phrase, cache=None, save=True):
    """Return {'@id':..., 'schema:name':...} for the best FAST match, else None.
    Prefers a case-insensitive exact match on the authority label; otherwise the
    top suggestion whose label starts with the phrase."""
    phrase = (phrase or "").strip()
    if not phrase:
        return None
    own_cache = cache is None
    if own_cache:
        cache = _load_cache()
    if phrase in cache:
        return cache[phrase]

    result = None
    try:
        data = _query(phrase)
        docs = data.get("response", {}).get("docs", [])
        low = phrase.lower()
        exact = next((d for d in docs if d.get("auth", "").lower() == low), None)

        def clean_prefix(d):
            # accept a prefix match only at a real boundary: end, "--" subdivision,
            # or " (" qualifier — rejects e.g. "Hong Kong" -> "Hong Kong Museum of Art".
            auth = d.get("auth", "")
            if not auth.lower().startswith(low):
                return False
            rest = auth[len(phrase):]
            return rest == "" or rest.startswith("--") or rest.startswith(" (")

        chosen = exact or next((d for d in docs if clean_prefix(d)), None)
        if chosen:
            result = {"@id": _fast_url(chosen["idroot"][0]), "schema:name": chosen["auth"]}
    except Exception as e:
        print(f"  ! FAST lookup failed for {phrase!r}: {e}", file=sys.stderr)
        return None  # don't cache transient failures

    cache[phrase] = result
    if own_cache and save:
        _save_cache(cache)
    time.sleep(0.2)  # be polite to the API
    return result


if __name__ == "__main__":
    # CLI: resolve each arg, print the mapping. Also seeds the content-type facet terms.
    terms = sys.argv[1:] or ["Photographs", "Menus", "Restaurants", "Chinese Americans",
                             "Chinese restaurants", "Ephemera"]
    cache = _load_cache()
    for t in terms:
        r = resolve(t, cache=cache, save=False)
        print(f"{t!r:40} -> {r}")
    _save_cache(cache)
