"""
Test Offline Mode - CSV-Only Pipeline Test
=============================================

Demonstrates the pipeline processing from existing CSV data only.
No API calls, no cache reads - purely local data processing.

Loads professors from the combined CSV, classifies research areas,
computes pickability, and displays the top 10 by venue paper count.

Usage:
    python test_offline.py [--top N]
"""

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = DATA_DIR / "output"
RESULTS_DIR = ROOT / "results"
CONFIG_FILE = ROOT / "config.json"

UNKNOWN_AREA = "Other"


def classify(text, target_areas, multi=True):
    if not text:
        return UNKNOWN_AREA
    low = text.lower()
    if multi:
        matched = []
        for area, keywords in target_areas.items():
            if any(kw in low for kw in keywords):
                matched.append(area)
        return ";".join(matched) if matched else UNKNOWN_AREA
    best_area = UNKNOWN_AREA
    best_score = 0
    for area, keywords in target_areas.items():
        score = sum(1 for kw in keywords if kw in low)
        if score > best_score:
            best_score = score
            best_area = area
    return best_area


def main():
    top_n = 10
    if "--top" in sys.argv:
        top_n = int(sys.argv[sys.argv.index("--top") + 1])

    cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    target_areas = cfg["target_areas"]
    pick_cfg = cfg["is_pickable"]

    combined_path = OUTPUT_DIR / "combined.csv"
    final_path = OUTPUT_DIR / "final_professor_results.csv"

    print("=" * 100)
    print("  OFFLINE TEST - CSV-Only Pipeline Test")
    print("  No API calls, no cache reads - purely local processing")
    print("=" * 100)
    print()

    rows = []
    if final_path.exists():
        with open(final_path, newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        print(f"  Loaded {len(rows)} rows from final_professor_results.csv")
        venue_col = "Venues"
        papers_col = "Number_of_Top_Venue_Papers"
    elif combined_path.exists():
        with open(combined_path, newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        print(f"  Loaded {len(rows)} rows from combined.csv")
        venue_col = "Matched_venues"
        papers_col = "N_target_pubs"
    else:
        print("[error] No data CSVs found in data/output/")
        sys.exit(1)

    ranked = sorted(rows, key=lambda r: int(r.get(papers_col) or 0), reverse=True)
    top = ranked[:top_n]

    print(f"  Target areas: {list(target_areas.keys())}")
    print(f"  Pickable rules: R1={pick_cfg.get('require_rank_r1')}, "
          f"min_pubs={pick_cfg.get('min_target_pubs')}, "
          f"exclude_other={pick_cfg.get('exclude_other_area')}")
    print()

    results = []
    for i, row in enumerate(top, 1):
        name = row.get("Professor") or row.get("Professor name", "")
        school = row.get("University", "")
        rank = row.get("Rank", "")
        research = row.get("Research area", "")
        venues_str = row.get(venue_col, "")
        n_pubs = int(row.get(papers_col) or 0)
        has_top = row.get("Has_Top_Venue_2024_2026", "")
        h_index = row.get("h_index", "")
        citations = row.get("total_citations", "")
        profile_url = row.get("profile_url", "")
        email = row.get("Email", "")

        rec_classified = classify(research, target_areas)

        is_pickable = True
        if pick_cfg.get("require_rank_r1"):
            is_pickable = is_pickable and rank == "r1"
        if pick_cfg.get("exclude_other_area"):
            areas = [a.strip() for a in rec_classified.split(";")]
            is_pickable = is_pickable and any(a != UNKNOWN_AREA for a in areas)
        min_pubs = pick_cfg.get("min_target_pubs")
        if min_pubs is not None:
            is_pickable = is_pickable and n_pubs >= min_pubs

        results.append({
            "rank": i, "name": name, "school": school,
            "orig_research": research, "rec_classified": rec_classified,
            "class_match": "MATCH" if rec_classified == research else "RECLASSIFIED",
            "venues": venues_str, "n_pubs": n_pubs,
            "has_top": has_top, "pickable": "TRUE" if is_pickable else "FALSE",
            "h_index": h_index, "citations": citations,
            "profile_url": profile_url, "email": email,
        })

    print(f"  {'#':>2s}  {'Professor':<35s}  {'University':<35s}  {'Pubs':>4s}  {'Pick':>5s}  {'Research Area'}")
    print("  " + "-" * 130)
    for r in results:
        print(f"  {r['rank']:2d}  {r['name']:<35s}  {r['school']:<35s}  {r['n_pubs']:>4d}  {r['pickable']:>5s}  {r['orig_research']}")

    print()
    print("=" * 100)
    print("  CLASSIFICATION VERIFICATION")
    print("=" * 100)
    match_count = sum(1 for r in results if r["class_match"] == "MATCH")
    reclass_count = sum(1 for r in results if r["class_match"] == "RECLASSIFIED")
    pickable_count = sum(1 for r in results if r["pickable"] == "TRUE")

    print(f"  Professors tested:          {len(results)}")
    print(f"  Classification match:       {match_count}/{len(results)}")
    print(f"  Reclassified:               {reclass_count}/{len(results)}")
    print(f"  Pickable:                   {pickable_count}/{len(results)}")
    print()

    if reclass_count > 0:
        print("  RECLASSIFIED PROFESSORS:")
        for r in results:
            if r["class_match"] == "RECLASSIFIED":
                print(f"    {r['name']}: '{r['orig_research']}' -> '{r['rec_classified']}'")
        print()

    print("  TOP PROFESSOR DETAILS:")
    print()
    for r in results:
        print(f"  {r['name']}")
        print(f"    University:    {r['school']}")
        print(f"    Rank:          {r['rank']}")
        print(f"    Research:      {r['orig_research']}")
        print(f"    Venues:        {r['venues'] or 'none'}")
        print(f"    Venue papers:  {r['n_pubs']}")
        print(f"    Pickable:      {r['pickable']}")
        if r["h_index"]:
            print(f"    h-index:       {r['h_index']}")
        if r["citations"]:
            print(f"    Citations:     {r['citations']}")
        if r["profile_url"]:
            print(f"    Profile:       {r['profile_url']}")
        print()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "test_offline_results.csv"
    with open(out_path, "w", newline="", encoding="utf-8-sig") as fh:
        fields = ["Rank", "Professor", "University", "Rank_Level", "Original_Research",
                  "Reclassified_Research", "Classification_Match",
                  "Venues", "Venue_Papers", "Has_Top_Venue", "Is_Pickable",
                  "h_index", "Total_Citations", "Profile_URL", "Email"]
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            writer.writerow({
                "Rank": r["rank"], "Professor": r["name"], "University": r["school"],
                "Rank_Level": r["school"] and r["venues"],
                "Original_Research": r["orig_research"],
                "Reclassified_Research": r["rec_classified"],
                "Classification_Match": r["class_match"],
                "Venues": r["venues"], "Venue_Papers": r["n_pubs"],
                "Has_Top_Venue": r["has_top"], "Is_Pickable": r["pickable"],
                "h_index": r["h_index"], "Total_Citations": r["citations"],
                "Profile_URL": r["profile_url"], "Email": r["email"],
            })
    print(f"  Results saved to: {out_path}")
    print("=" * 100)


if __name__ == "__main__":
    main()
