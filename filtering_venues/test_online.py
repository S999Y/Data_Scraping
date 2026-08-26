"""
Test Online Mode - Cached API Data Test
=========================================

Demonstrates the full venue matching pipeline using cached OpenAlex API data.
Loads the top 10 professors (by venue paper count) from the existing results,
re-runs venue matching from cached author/works data, and displays outcomes.

No live API calls are made - all data comes from disk cache.

Usage:
    python test_online.py [--top N]
"""

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = DATA_DIR / "output"
CACHE_DIR = DATA_DIR / "cache"
AUTHOR_CACHE_DIR = CACHE_DIR / "author_matches"
WORKS_CACHE_DIR = CACHE_DIR / "venue_works"
RESULTS_DIR = ROOT / "results"
CONFIG_FILE = ROOT / "config.json"


def slugify(text):
    return "".join(c if c.isalnum() else "_" for c in text.lower()).strip("_")


def norm(text):
    import re
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def build_aliases(cfg):
    return {short: [norm(a) for a in aliases] for short, aliases in cfg["target_venues"].items()}


def match_venue(source, aliases):
    if not source:
        return None
    v = norm(source)
    for short, pats in aliases.items():
        for p in pats:
            if p and p in v:
                return short
    return None


def load_cached_author(school, name):
    path = AUTHOR_CACHE_DIR / f"{slugify(school)}_{slugify(name)}.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return None


def load_cached_works(school, name):
    path = WORKS_CACHE_DIR / f"{slugify(school)}_{slugify(name)}.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data.get("works", {})
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def main():
    top_n = 10
    if "--top" in sys.argv:
        top_n = int(sys.argv[sys.argv.index("--top") + 1])

    cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    aliases = build_aliases(cfg)

    final_csv = OUTPUT_DIR / "final_professor_results.csv"
    if not final_csv.exists():
        print(f"[error] {final_csv} not found")
        sys.exit(1)

    with open(final_csv, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))

    ranked = sorted(rows, key=lambda r: int(r.get("Number_of_Top_Venue_Papers") or 0), reverse=True)
    top = ranked[:top_n]

    print("=" * 100)
    print("  ONLINE TEST - Cached API Data Pipeline Test")
    print("  Re-runs venue matching from cached author matches and works data")
    print("=" * 100)
    print()

    results = []
    for i, row in enumerate(top, 1):
        name = row.get("Professor", "")
        school = row.get("University", "")
        orig_venues = row.get("Venues", "")
        orig_papers = int(row.get("Number_of_Top_Venue_Papers") or 0)
        author_status = row.get("Author_Status", "")
        author_id = row.get("OpenAlex_Author_ID", "")
        research = row.get("Research area", "")

        author_cache = load_cached_author(school, name)
        works_cache = load_cached_works(school, name)

        all_works = []
        for aid_key, works_list in works_cache.items():
            all_works.extend(works_list)

        matched_venues = set()
        matched_papers = []
        for w in all_works:
            venue = match_venue(w.get("source", ""), aliases)
            if venue:
                matched_venues.add(venue)
                matched_papers.append(w)

        re_matched = sorted(matched_venues)
        re_count = len(matched_papers)

        status_icon = "CACHED" if author_cache else "NO_CACHE"
        paper_match = "OK" if re_count == orig_papers else f"MISMATCH ({re_count} vs {orig_papers})"

        results.append({
            "rank": i, "name": name, "school": school,
            "research": research, "author_status": author_status,
            "author_id": author_id, "cache_status": status_icon,
            "orig_venues": orig_venues, "orig_papers": orig_papers,
            "re_venues": ";".join(re_matched), "re_papers": re_count,
            "verification": paper_match,
            "matched_papers": matched_papers,
        })

    print(f"  {'#':>2s}  {'Professor':<35s}  {'University':<35s}  {'Status':<10s}  {'Papers':>6s}  {'Venues'}")
    print("  " + "-" * 130)
    for r in results:
        print(f"  {r['rank']:2d}  {r['name']:<35s}  {r['school']:<35s}  {r['author_status']:<10s}  {r['re_papers']:>6d}  {r['re_venues']}")

    print()
    print("=" * 100)
    print("  VERIFICATION SUMMARY")
    print("=" * 100)
    cached_count = sum(1 for r in results if r["cache_status"] == "CACHED")
    matched_count = sum(1 for r in results if r["re_papers"] > 0)
    ok_count = sum(1 for r in results if r["verification"] == "OK")
    print(f"  Professors tested:          {len(results)}")
    print(f"  With cached author data:    {cached_count}/{len(results)}")
    print(f"  With venue matches:         {matched_count}/{len(results)}")
    print(f"  Exact paper count match:    {ok_count}/{len(results)}")

    print()
    print("  DETAILED PAPER LISTINGS:")
    print()
    for r in results:
        if r["matched_papers"]:
            print(f"  {r['name']} ({r['school']})")
            for p in r["matched_papers"][:5]:
                src = p.get("source", "unknown")
                yr = p.get("year", "?")
                title = (p.get("title", "untitled"))[:70]
                print(f"    [{yr}] {src:<25s}  {title}")
            if len(r["matched_papers"]) > 5:
                print(f"    ... and {len(r['matched_papers']) - 5} more")
            print()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "test_online_results.csv"
    with open(out_path, "w", newline="", encoding="utf-8-sig") as fh:
        fields = ["Rank", "Professor", "University", "Research_area", "Author_Status",
                  "Cache_Status", "Original_Venues", "Original_Papers",
                  "Recomputed_Venues", "Recomputed_Papers", "Verification"]
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            writer.writerow({
                "Rank": r["rank"], "Professor": r["name"], "University": r["school"],
                "Research_area": r["research"], "Author_Status": r["author_status"],
                "Cache_Status": r["cache_status"],
                "Original_Venues": r["orig_venues"], "Original_Papers": r["orig_papers"],
                "Recomputed_Venues": r["re_venues"], "Recomputed_Papers": r["re_papers"],
                "Verification": r["verification"],
            })
    print(f"  Results saved to: {out_path}")
    print("=" * 100)


if __name__ == "__main__":
    main()
