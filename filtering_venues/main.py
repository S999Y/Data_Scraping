"""
CS Faculty Research Profiling System - Unified Pipeline
=======================================================

Scrapes CS faculty from 84 US universities, enriches with OpenAlex publication
data, matches against 11 top-tier AI/ML/CV/NLP venues, and determines which
professors are "pickable" (R1 rank + relevant research area + venue pubs).

Usage:
    python main.py --mode online [--limit N] [--school "Name"]
    python main.py --mode offline [--limit N]
    python main.py --mode scrape [--limit N] [--school "Name"] [--no-profiles]
"""

import csv
import json
import re
import sys
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from derive.research_area import classify, UNKNOWN_AREA
from derive.scoring import build_row
from output.writers import FIELDS, write_csv
from publishers.openalex import OpenAlexClient
from scrapers import ROR_MAP, make_scraper

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = DATA_DIR / "output"
RESULTS_DIR = ROOT / "results"
CACHE_DIR = DATA_DIR / "cache"
AUTHOR_CACHE_DIR = CACHE_DIR / "author_matches"
WORKS_CACHE_DIR = CACHE_DIR / "venue_works"

UNIVERSITY_JSON = DATA_DIR / "university_data.json"
SCHOOL_CONFIG = DATA_DIR / "school_config.json"
ROR_MAP_FILE = DATA_DIR / "ror_map.json"
API_KEYS_FILE = DATA_DIR / "api" / "api_key.txt"
CONFIG_FILE = ROOT / "config.json"
PROGRESS_FILE = DATA_DIR / "progress.json"
RESEARCH_AREAS_CSV = OUTPUT_DIR / "research_areas.csv"
COMBINED_CSV = OUTPUT_DIR / "combined.csv"

YEAR_FROM, YEAR_TO = 2024, 2026
STATUS_MATCHED = "MATCHED"
STATUS_REVIEW = "REVIEW"
STATUS_NOT_FOUND = "NOT_FOUND"


def slugify(text):
    return "".join(c if c.isalnum() else "_" for c in text.lower()).strip("_")


def norm(text):
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def clean_prof_name(name):
    clean = (name or "").split(",")[0].strip()
    clean = re.sub(r"\s+", " ", clean).strip()
    tokens = set(re.findall(r"[a-z0-9]+", norm(clean)))
    return clean, tokens


def load_api_keys():
    keys = []
    if API_KEYS_FILE.exists():
        keys = [k.strip() for k in API_KEYS_FILE.read_text(encoding="utf-8").splitlines() if k.strip()]
    cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    extra = cfg.get("openalex", {}).get("api_key", [])
    if isinstance(extra, list):
        keys.extend([k for k in extra if k])
    elif extra:
        keys.append(extra)
    return keys


def load_config():
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))


def load_schools():
    data = json.loads(UNIVERSITY_JSON.read_text(encoding="utf-8"))
    return [
        {
            "university_name": (d.get("university_name", "")).replace("\u2013", "-").replace("\u2014", "-").strip(),
            "rank": str(d.get("rank", "") or "").strip(),
            "rank_place": d.get("rank_place"),
            "faculty_url": (d.get("faculty_url", "") or "").strip(),
        }
        for d in data
        if (d.get("university_name") or "").strip()
    ]


def load_configs():
    if SCHOOL_CONFIG.exists():
        return json.loads(SCHOOL_CONFIG.read_text(encoding="utf-8"))
    return {}


def load_progress():
    if PROGRESS_FILE.exists():
        try:
            return set(json.loads(PROGRESS_FILE.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            return set()
    return set()


def save_progress(done):
    PROGRESS_FILE.write_text(json.dumps(sorted(done), ensure_ascii=False, indent=1), encoding="utf-8")


def load_existing_rows():
    rows = []
    if COMBINED_CSV.exists():
        try:
            with open(COMBINED_CSV, newline="", encoding="utf-8-sig") as fh:
                reader = csv.DictReader(fh)
                rows = [dict(r) for r in reader]
        except (csv.Error, OSError):
            rows = []
    return rows


# ---------------------------------------------------------------------------
# Phase 1: Scrape Faculty
# ---------------------------------------------------------------------------

def run_scrape(cfg, limit=None, school_filter=None, follow_profiles=True):
    site_delay = cfg["scrape"]["site_delay_seconds"]
    schools = load_schools()
    configs = load_configs()
    done = load_progress()
    rows = load_existing_rows()

    if school_filter:
        norm_f = school_filter.replace("\u2013", "-").replace("\u2014", "-").strip()
        schools = [s for s in schools if s["university_name"] == norm_f]
        done = {d for d in done if d.replace("\u2013", "-").replace("\u2014", "-").strip() != norm_f}
        rows = [r for r in rows if r.get("University") != norm_f]

    print(f"[scrape] {len(schools)} universities; {len(done)} already done")

    for i, school in enumerate(schools, 1):
        name = school["university_name"]
        if name in done:
            print(f"  [skip] {i}/{len(schools)} {name}")
            continue
        url = school["faculty_url"]
        print(f"  [scrape] {i}/{len(schools)} {name}  {url}")
        if not url:
            print("    [error] no faculty_url (pending)")
            continue
        config = dict(configs.get(name, {}))
        if not follow_profiles:
            config["follow_profiles"] = False
        scraper = make_scraper(name, school["rank"], url, config=config, delay=site_delay)
        try:
            profiles = scraper.scrape()
        except Exception as exc:
            print(f"    [error] scrape failed: {exc} (pending)")
            continue
        if limit:
            profiles = profiles[:limit]
        print(f"    found {len(profiles)} faculty")

        for profile in profiles:
            row = build_row(name, school["rank"], profile, None, cfg)
            rows.append(row)
        write_csv(COMBINED_CSV, rows)
        print(f"    wrote {COMBINED_CSV.name} ({len(rows)} rows total)")
        if not profiles or limit:
            print("    [pending] school NOT marked done (retry possible)")
            continue
        done.add(name)
        save_progress(done)

    print(f"[done] combined -> {COMBINED_CSV} ({len(rows)} rows)")
    return rows


# ---------------------------------------------------------------------------
# Phase 2: Venue Matching (with OpenAlex enrichment)
# ---------------------------------------------------------------------------

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


class AuthorResolver:
    def __init__(self, client, refresh=False):
        self.client = client
        self.refresh = refresh
        self._ror_map = dict(ROR_MAP)
        if ROR_MAP_FILE.exists():
            try:
                self._ror_map.update(json.loads(ROR_MAP_FILE.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                pass
        self._lock = threading.Lock()

    def ror_for(self, school):
        if school in self._ror_map:
            return self._ror_map[school]
        with self._lock:
            if school in self._ror_map:
                return self._ror_map[school]
            ror = self.client.find_institution(school)
            if ror:
                self._ror_map[school] = ror
                ROR_MAP_FILE.write_text(
                    json.dumps(self._ror_map, ensure_ascii=False, indent=1), encoding="utf-8",
                )
            return ror

    def resolve(self, name, school):
        cache_path = AUTHOR_CACHE_DIR / f"{slugify(school)}_{slugify(name)}.json"
        if not self.refresh and cache_path.exists():
            try:
                return json.loads(cache_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass

        clean, tokens = clean_prof_name(name)
        ror = self.ror_for(school)
        payload = self._decide(
            self._score(self.client.search_authors(clean), clean, tokens, ror, norm(school))
        )

        AUTHOR_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        return payload

    @staticmethod
    def _score(candidates, clean, tokens, ror, school_norm):
        scored = []
        for a in candidates:
            disp = (a.get("display_name") or "").strip()
            dn = norm(disp)
            dtoks = set(re.findall(r"[a-z0-9]+", dn))
            name_score = 0.0
            if clean and dn == norm(clean):
                name_score = 1.0
            elif tokens and tokens <= dtoks:
                name_score = 0.7
            elif clean and dn and norm(clean) in dn:
                name_score = 0.6

            inst_score, matched_inst = 0.0, ""
            for inst in a.get("last_known_institutions") or []:
                iid = inst.get("id") or ""
                iror = inst.get("ror") or ""
                iname = norm(inst.get("display_name") or "")
                if ror and (iid == ror or iror == ror):
                    inst_score = 1.0
                    matched_inst = inst.get("display_name") or iror
                    break
                if school_norm and iname and (
                    iname == school_norm or iname in school_norm or school_norm in iname
                ):
                    inst_score = 1.0
                    matched_inst = inst.get("display_name") or ""
                    break

            scored.append({
                "id": a.get("id") or "",
                "display_name": disp,
                "works_count": a.get("works_count") or 0,
                "institutions": [
                    i.get("display_name")
                    for i in (a.get("last_known_institutions") or [])
                    if i.get("display_name")
                ],
                "name_score": name_score,
                "inst_score": inst_score,
                "matched_inst": matched_inst,
                "score": round(name_score * 3 + inst_score * 5, 3),
            })
        scored.sort(key=lambda s: (s["inst_score"], s["score"], s["works_count"]), reverse=True)
        return scored

    @staticmethod
    def _decide(scored):
        if not scored:
            return {
                "status": STATUS_NOT_FOUND, "author": None, "runner": None,
                "merge_ids": [], "score": 0.0, "matched_institution": "",
            }
        inst_cands = [s for s in scored if s["inst_score"] > 0]
        if inst_cands:
            best = inst_cands[0]
            return {
                "status": STATUS_MATCHED, "author": best,
                "runner": inst_cands[1] if len(inst_cands) > 1 else None,
                "merge_ids": [s["id"] for s in inst_cands],
                "score": best["score"],
                "matched_institution": best["matched_inst"] or (
                    best["institutions"][0] if best["institutions"] else ""
                ),
                "candidates": scored[:5],
            }
        best, second = scored[0], (scored[1] if len(scored) > 1 else None)
        status = STATUS_MATCHED if best["name_score"] >= 0.7 and (
            second is None or second["name_score"] < 0.7
        ) else STATUS_REVIEW
        return {
            "status": status, "author": best, "runner": second,
            "merge_ids": [best["id"]] if best["id"] else [],
            "score": best["score"],
            "matched_institution": best["institutions"][0] if best["institutions"] else "",
            "candidates": scored[:5],
        }


def extract_work(w):
    src = (w.get("primary_location") or {}).get("source") or {}
    return {
        "work_id": w.get("id") or "",
        "title": w.get("display_name") or "",
        "doi": w.get("doi") or "",
        "year": w.get("publication_year"),
        "type": w.get("type") or "",
        "source": src.get("display_name") or "",
        "source_id": src.get("id") or "",
    }


_works_cache_locks = {}


def load_or_fetch_works(client, school, name, author_id, refresh):
    cache_path = WORKS_CACHE_DIR / f"{slugify(school)}_{slugify(name)}.json"
    with _works_cache_locks.setdefault(str(cache_path), threading.Lock()):
        data = {}
        if not refresh and cache_path.exists():
            try:
                payload = json.loads(cache_path.read_text(encoding="utf-8"))
                data = payload.get("works") or {}
            except (json.JSONDecodeError, OSError):
                data = {}
        if author_id not in data:
            works = [extract_work(w) for w in client.get_works_filtered(author_id, YEAR_FROM, YEAR_TO)]
            data[author_id] = works
            WORKS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(
                json.dumps({"works": data}, ensure_ascii=False, indent=1), encoding="utf-8",
            )
        return data.get(author_id, [])


def recompute_is_pickable(row, n_target_pubs, cfg):
    pick_cfg = cfg["is_pickable"]
    pick = True
    if pick_cfg.get("require_rank_r1"):
        pick = pick and row.get("Rank", "") == "r1"
    if pick_cfg.get("exclude_other_area"):
        areas = [a.strip() for a in row.get("Research area", "").split(";")]
        pick = pick and any(a != UNKNOWN_AREA for a in areas)
    min_pubs = pick_cfg.get("min_target_pubs")
    if min_pubs is not None:
        try:
            n = int(n_target_pubs or 0)
        except (TypeError, ValueError):
            n = 0
        pick = pick and n >= min_pubs
    return "TRUE" if pick else "FALSE"


def write_named_csv(path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


# ---------------------------------------------------------------------------
# Venue matching main function
# ---------------------------------------------------------------------------

def run_venue_match(cfg, limit=None, school_filter=None, refresh=False):
    aliases = build_aliases(cfg)
    oa = cfg["openalex"]
    api_keys = load_api_keys()

    client = OpenAlexClient(
        mailto=oa.get("mailto") or None,
        delay=oa["delay_seconds"],
        per_page=oa["per_page"],
        max_works=oa["max_works"],
        rate_limit=oa.get("rate_limit", 8),
        api_key=api_keys if api_keys else (oa.get("api_key") or oa.get("api_keys")),
    )
    resolver = AuthorResolver(client, refresh)

    with open(RESEARCH_AREAS_CSV, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    print(f"[venue_match] {len(rows)} rows")

    if school_filter:
        def _norm(s):
            return s.replace("\u2013", "-").replace("\u2014", "-").strip()
        rows = [r for r in rows if _norm(r.get("University", "")) == _norm(school_filter)]
        print(f"  [filter] {len(rows)} rows for {school_filter}")
    if limit:
        rows = rows[:limit]

    items = list(enumerate(rows))

    def process(item):
        i, row = item
        name = row.get("Professor name", "") or ""
        school = row.get("University", "") or ""
        res = resolver.resolve(name, school)
        author = res.get("author") or {}
        works = []
        by_work_id = {}
        for aid in res.get("merge_ids") or []:
            for w in load_or_fetch_works(client, school, name, aid, refresh):
                if w["work_id"]:
                    by_work_id[w["work_id"]] = w
        works = list(by_work_id.values())
        matches = []
        for w in works:
            venue = match_venue(w["source"], aliases)
            if venue:
                matches.append({"venue": venue, "venue_raw": w["source"], **w})
        venues = sorted({m["venue"] for m in matches})
        years = sorted({str(m["year"]) for m in matches})
        n_pubs = len(matches)
        row["Matched_venues"] = ";".join(venues)
        row["N_target_pubs"] = str(n_pubs)
        row["Total_publications"] = str(len(works))
        row["is_pickable"] = recompute_is_pickable(row, n_pubs, cfg)
        return {
            "row": row, "school": school, "name": name, "author": author,
            "status": res.get("status", ""), "score": res.get("score", 0.0),
            "matched_institution": res.get("matched_institution", ""),
            "matches": matches, "venues": venues, "years": years,
            "n_pubs": n_pubs, "n_works": len(works),
        }

    ordered = [None] * len(items)
    results = [None] * len(items)
    done_count = 0
    pool = ThreadPoolExecutor(max_workers=oa.get("max_workers", 4))
    futures = {pool.submit(process, item): i for i, item in enumerate(items)}
    try:
        for fut in as_completed(futures):
            i = futures[fut]
            res = fut.result()
            ordered[i] = res["row"]
            results[i] = res
            done_count += 1
            if done_count % 25 == 0:
                print(f"  {done_count}/{len(items)} processed")
    except KeyboardInterrupt:
        print("\n[interrupt] partial results written")
        for f in futures:
            f.cancel()
        pool.shutdown(wait=False, cancel_futures=True)
        ordered = [r for r in ordered if r is not None]
        results = [r for r in results if r is not None]
    finally:
        pool.shutdown(wait=False)

    ordered = [r for r in ordered if r is not None]
    results = [r for r in results if r is not None]

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(RESULTS_DIR / "combined.csv", ordered)
    print(f"  [csv] {len(ordered)} rows -> results/combined.csv")

    author_fields = ["Professor", "University", "Rank", "OpenAlex_Author_ID", "OpenAlex_Name", "Matched_Institution", "Score", "Status"]
    author_rows = [
        {
            "Professor": r["name"], "University": r["school"], "Rank": r["row"].get("Rank", ""),
            "OpenAlex_Author_ID": (r["author"].get("id") or "").replace("https://openalex.org/", ""),
            "OpenAlex_Name": r["author"].get("display_name", ""),
            "Matched_Institution": r["matched_institution"],
            "Score": r["score"], "Status": r["status"],
        }
        for r in results
    ]
    write_named_csv(RESULTS_DIR / "author_matches.csv", author_fields, author_rows)

    paper_fields = ["Professor", "University", "Rank", "OpenAlex_Author_ID", "Venue", "Venue_Raw", "Year", "Paper_Title", "DOI", "OpenAlex_Work_ID"]
    paper_rows = []
    for r in results:
        aid = (r["author"].get("id") or "").replace("https://openalex.org/", "")
        for m in r["matches"]:
            paper_rows.append({
                "Professor": r["name"], "University": r["school"], "Rank": r["row"].get("Rank", ""),
                "OpenAlex_Author_ID": aid, "Venue": m["venue"], "Venue_Raw": m["venue_raw"],
                "Year": m["year"], "Paper_Title": m["title"], "DOI": m["doi"],
                "OpenAlex_Work_ID": m["work_id"].replace("https://openalex.org/", ""),
            })
    write_named_csv(RESULTS_DIR / "top_venue_papers.csv", paper_fields, paper_rows)

    final_fields = ["Professor", "University", "Rank", "Research area", "Has_Top_Venue_2024_2026", "Venues", "Number_of_Top_Venue_Papers", "Years", "OpenAlex_Author_ID", "Author_Status"]
    final_rows = [
        {
            "Professor": r["name"], "University": r["school"], "Rank": r["row"].get("Rank", ""),
            "Research area": r["row"].get("Research area", ""),
            "Has_Top_Venue_2024_2026": (
                "REVIEW" if r["status"] == STATUS_REVIEW else ("YES" if r["n_pubs"] else "NO")
            ),
            "Venues": ";".join(r["venues"]), "Number_of_Top_Venue_Papers": r["n_pubs"],
            "Years": ";".join(r["years"]),
            "OpenAlex_Author_ID": (r["author"].get("id") or "").replace("https://openalex.org/", ""),
            "Author_Status": r["status"],
        }
        for r in results
    ]
    write_named_csv(RESULTS_DIR / "final_professor_results.csv", final_fields, final_rows)

    by_status = Counter(r["status"] for r in results)
    print(f"  [done] {len(results)} rows")
    print(f"  author status: {dict(by_status)}")
    print(f"  matched professors: {sum(1 for r in results if r['n_pubs'])}")
    venue_counts = Counter(m["venue"] for r in results for m in r["matches"])
    for venue, n in venue_counts.most_common():
        print(f"    {n:5d}  {venue}")

    return results


# ---------------------------------------------------------------------------
# Phase 3: Offline mode (process from existing CSVs)
# ---------------------------------------------------------------------------

def run_offline(cfg, limit=None):
    """Process existing CSV data without making any API calls."""
    print("[offline] Processing from existing CSV data (no API calls)")

    combined_path = OUTPUT_DIR / "combined.csv"
    if not combined_path.exists():
        print(f"  [error] {combined_path} not found. Run scrape first.")
        return []

    with open(combined_path, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    print(f"  loaded {len(rows)} rows from {combined_path.name}")

    if limit:
        rows = rows[:limit]

    aliases = build_aliases(cfg)
    results = []

    for row in rows:
        name = row.get("Professor name", "") or ""
        school = row.get("University", "") or ""
        n_pubs = int(row.get("N_target_pubs") or 0)
        venues_str = row.get("Matched_venues") or ""
        total_pubs = int(row.get("Total_publications") or 0)

        results.append({
            "row": row, "school": school, "name": name,
            "author": {}, "status": "", "score": 0.0,
            "matched_institution": "",
            "matches": [], "venues": venues_str.split(";") if venues_str else [],
            "years": [], "n_pubs": n_pubs, "n_works": total_pubs,
        })

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(RESULTS_DIR / "offline_combined.csv", rows)
    print(f"  [csv] {len(rows)} rows -> results/offline_combined.csv")

    ranked = sorted(results, key=lambda r: r["n_pubs"], reverse=True)
    print(f"\n  Top 10 by venue papers:")
    for i, r in enumerate(ranked[:10], 1):
        v = ";".join(r["venues"]) if r["venues"] else "none"
        print(f"  {i:2d}. {r['name']:40s} | {r['school']:40s} | pubs={r['n_pubs']:>3d} | {v}")

    return results


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    args = sys.argv[1:]
    mode = "online"
    if "--mode" in args:
        idx = args.index("--mode")
        if idx + 1 < len(args):
            mode = args[idx + 1]

    limit = None
    if "--limit" in args:
        limit = int(args[args.index("--limit") + 1])

    school_filter = None
    if "--school" in args:
        school_filter = args[args.index("--school") + 1]

    follow_profiles = "--no-profiles" not in args
    refresh = "--refresh" in args

    cfg = load_config()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"=" * 70)
    print(f"  CS Faculty Research Profiling System")
    print(f"  Mode: {mode.upper()}")
    print(f"  Limit: {limit or 'all'}")
    if school_filter:
        print(f"  School: {school_filter}")
    print(f"=" * 70)

    if mode == "scrape":
        run_scrape(cfg, limit=limit, school_filter=school_filter, follow_profiles=follow_profiles)

    elif mode == "online":
        if not RESEARCH_AREAS_CSV.exists():
            print("[info] No existing research_areas.csv found.")
            print("  Running scrape first to generate data...")
            run_scrape(cfg, limit=limit, school_filter=school_filter, follow_profiles=follow_profiles)
        print("\n[phase 2] Running venue matching with OpenAlex enrichment...")
        run_venue_match(cfg, limit=limit, school_filter=school_filter, refresh=refresh)

    elif mode == "offline":
        run_offline(cfg, limit=limit)

    else:
        print(f"[error] Unknown mode: {mode}")
        print("  Valid modes: online, offline, scrape")
        sys.exit(1)

    print(f"\n{'=' * 70}")
    print(f"  Pipeline complete. Results in: {RESULTS_DIR}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    sys.exit(main())
