"""Fetch professor publication data from OpenAlex API and produce enriched CSVs.

Reads professor names from bundled CSVs, queries OpenAlex for author metadata
(h-index, citations, publication counts, venue matches), and writes an enriched
CSV into data/ so that merge_ai_professors.py can produce the final output.

Usage:
    python openalex_fetcher.py [--limit 10] [--delay 0.15]

Requires: pandas, requests (see requirements.txt)
"""

import argparse
import os
import re
import sys
import time

import pandas as pd
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_INPUT_DIR = os.path.join(BASE_DIR, "data")

# Top AI/ML/NLP/CV venues — match both abbreviations and full OpenAlex names.
TARGET_VENUES = {
    "NeurIPS", "NIPS", "ICML", "ICLR", "CVPR", "ICCV", "ECCV",
    "AAAI", "ACL", "EMNLP", "NAACL", "IJCAI", "ACM MM", "SIGIR",
    "KDD", "WWW", "WACV",
}

# Substring patterns to match OpenAlex full venue names.
VENUE_PATTERNS = [
    ("NeurIPS", ["Neural Information Processing Systems", "NeurIPS"]),
    ("ICML", ["International Conference on Machine Learning"]),
    ("ICLR", ["International Conference on Learning Representations"]),
    ("CVPR", ["Conference on Computer Vision and Pattern Recognition"]),
    ("ICCV", ["International Conference on Computer Vision"]),
    ("ECCV", ["European Conference on Computer Vision"]),
    ("AAAI", ["AAAI Conference", "Proceedings of the AAAI"]),
    ("ACL", ["Association for Computational Linguistics"]),
    ("EMNLP", ["Empirical Methods in Natural Language Processing", "EMNLP"]),
    ("NAACL", ["North American Chapter of the Association for Computational Linguistics", "NAACL"]),
    ("IJCAI", ["International Joint Conference on Artificial Intelligence", "IJCAI"]),
    ("SIGIR", ["SIGIR"]),
    ("KDD", ["KDD"]),
    ("WACV", ["Winter Conference on Applications of Computer Vision", "WACV"]),
]

VENUE_CANONICAL = {"NIPS": "NeurIPS"}

OPENALEX_AUTHOR_API = "https://api.openalex.org/authors"
OPENALEX_WORKS_API = "https://api.openalex.org/works"

# API keys (rotate on 429)
API_KEYS = [
    "wvoWDJ6Nkwq7IOsziMWbL3",
    "sGxHBh2UhR6vzdykLM3OUs",
    "N2yBzgYfEzX6l4rGmYpPVe",
]


def normalize_venue(name: str) -> str:
    name = name.strip()
    return VENUE_CANONICAL.get(name, name)


def match_venue(display_name: str) -> str | None:
    """Match an OpenAlex venue display_name to our target venue abbreviation."""
    if not display_name:
        return None
    dn = display_name.lower()
    # Direct abbreviation match
    for abbr in TARGET_VENUES:
        if abbr.lower() == dn:
            return VENUE_CANONICAL.get(abbr, abbr)
    # Full-name substring match
    for abbr, patterns in VENUE_PATTERNS:
        for pat in patterns:
            if pat.lower() in dn:
                return VENUE_CANONICAL.get(abbr, abbr)
    return None


def extract_openalex_id(url_or_id: str) -> str | None:
    if not url_or_id or pd.isna(url_or_id):
        return None
    m = re.search(r"A\d{7,}", str(url_or_id))
    return m.group(0) if m else None


def query_openalex_author(name: str, institution: str, session: requests.Session, api_key: str) -> dict | None:
    params = {"search": name, "per_page": 5, "mailto": "demo@university.edu"}
    if api_key:
        params["api_key"] = api_key
    try:
        resp = session.get(OPENALEX_AUTHOR_API, params=params, timeout=15)
        if resp.status_code == 429:
            print("    [rate limited, waiting 5s...]")
            time.sleep(5)
            resp = session.get(OPENALEX_AUTHOR_API, params=params, timeout=15)
        resp.raise_for_status()
        results = resp.json().get("results", [])
    except Exception as e:
        print(f"    [error: {e}]")
        return None

    if not results:
        return None

    inst_lower = institution.lower().strip()
    for r in results:
        for aff in (r.get("affiliations") or []):
            inst_name = (aff.get("institution") or {}).get("display_name", "").lower()
            if inst_lower in inst_name or inst_name in inst_lower:
                return r
    return results[0]


def fetch_venue_papers(author_id: str, session: requests.Session, api_key: str) -> list[dict]:
    venue_papers = []
    cursor = "*"
    fetched = 0

    while cursor and fetched < 300:
        params = {
            "filter": f"authorships.author.id:{author_id},publication_year:2020-2026",
            "per_page": 100,
            "cursor": cursor,
            "select": "id,publication_year,primary_location",
            "mailto": "demo@university.edu",
        }
        if api_key:
            params["api_key"] = api_key
        try:
            resp = session.get(OPENALEX_WORKS_API, params=params, timeout=15)
            if resp.status_code == 429:
                time.sleep(5)
                resp = session.get(OPENALEX_WORKS_API, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            break

        results = data.get("results", [])
        if not results:
            break

        for work in results:
            source = (work.get("primary_location") or {}).get("source") or {}
            vn = match_venue(source.get("display_name", ""))
            if vn:
                venue_papers.append({"venue": vn, "year": work.get("publication_year")})

        fetched += len(results)
        cursor = data.get("meta", {}).get("next_cursor")

    return venue_papers


def pick_demo_professors(limit: int) -> pd.DataFrame:
    """Pick well-known AI professors guaranteed to have rich OpenAlex data."""
    DEMO_PROFESSORS = [
        ("Percy Liang", "Stanford University"),
        ("Michael Jordan", "University of California, Berkeley"),
        ("Dawn Song", "University of California, Berkeley"),
        ("Pieter Abbeel", "University of California, Berkeley"),
        ("Daniela Rus", "Massachusetts Institute of Technology"),
        ("Inderjit Dhillon", "University of Texas at Austin"),
        ("Kuldeep S. Meel", "Georgia Institute of Technology"),
        ("Peter Stone", "University of Texas at Austin"),
        ("Yejin Choi", "University of Washington"),
        ("Tianlong Chen", "University of North Carolina at Chapel Hill"),
        ("Vincent Conitzer", "Carnegie Mellon University"),
        ("Alan Fern", "Oregon State University"),
        ("Tuomas Sandholm", "Carnegie Mellon University"),
        ("Xiaowei Jia", "University of Pittsburgh"),
        ("Jitendra Malik", "University of California, Berkeley"),
    ]
    rows = [{"Professor name": name, "University": uni} for name, uni in DEMO_PROFESSORS[:limit]]
    return pd.DataFrame(rows)


def enrich_professors(input_dir: str, delay: float, limit: int) -> None:
    api_key = API_KEYS[0]

    if limit:
        df = pick_demo_professors(limit)
        print(f"Demo mode: enriching {len(df)} selected professors...")
    else:
        frames = []
        for fname in ["combined.csv", "combined_faculty.csv"]:
            p = os.path.join(input_dir, fname)
            if os.path.exists(p):
                frames.append(pd.read_csv(p, dtype=str).fillna(""))
        if not frames:
            print("No input CSVs found in", input_dir)
            sys.exit(1)
        df = pd.concat(frames, ignore_index=True)
        df.columns = [c.strip() for c in df.columns]
        name_col = next((c for c in df.columns if "professor name" in c.lower()), "Professor name")
        uni_col = next((c for c in df.columns if c.lower() == "university"), "University")
        df = df.drop_duplicates(subset=[name_col, uni_col]).reset_index(drop=True)
        df = df.rename(columns={name_col: "Professor name", uni_col: "University"})
        print(f"Full mode: enriching {len(df)} professors from OpenAlex...")

    session = requests.Session()
    session.headers["User-Agent"] = "AIFilter/1.0 (mailto:demo@university.edu)"

    results = []
    for i, row in df.iterrows():
        name = str(row["Professor name"]).strip()
        uni = str(row["University"]).strip()

        author = query_openalex_author(name, uni, session, api_key)
        record = {
            "University": uni,
            "Rank": "r1",
            "Ranking": "",
            "Professor name": name,
            "Email": "",
            "Mail": "",
            "Lab link": "",
            "Research area": "Machine Learning",
            "is_pickable": "",
            "Matched_venues": "",
            "N_target_pubs": "0",
            "Total_publications": "0",
            "profile_url": "",
        }

        if author:
            record["Total_publications"] = str(author.get("works_count", ""))
            h = (author.get("summary_stats") or {}).get("h_index", "")
            record["profile_url"] = author.get("id", "")

            aid = extract_openalex_id(author.get("id", ""))
            if aid:
                venue_papers = fetch_venue_papers(aid, session, api_key)
                venues = sorted(set(p["venue"] for p in venue_papers))
                record["Matched_venues"] = ";".join(venues)
                record["N_target_pubs"] = str(len(venue_papers))

        npubs = record["N_target_pubs"]
        tag = f"  [{npubs} venue papers]" if int(npubs) > 0 else ""
        status = "found" if author else "NOT FOUND"
        print(f"  {i+1}/{len(df)}  {name} ({uni}) -- {status}{tag}")

        results.append(record)
        time.sleep(delay)

    out_df = pd.DataFrame(results)
    out_path = os.path.join(input_dir, "openalex_enriched.csv")
    out_df.to_csv(out_path, index=False, encoding="utf-8")

    matched = sum(1 for r in results if r["Matched_venues"])
    print(f"\nEnriched data saved to {out_path}")
    print(f"With venue papers: {matched}/{len(results)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch professor data from OpenAlex API")
    parser.add_argument("--input-dir", default=DEFAULT_INPUT_DIR, help="Directory containing input CSVs")
    parser.add_argument("--delay", type=float, default=0.15, help="Delay between API requests in seconds")
    parser.add_argument("--limit", type=int, default=10, help="Number of professors to enrich (demo mode). 0 = all.")
    args = parser.parse_args()

    enrich_professors(args.input_dir, args.delay, args.limit)


if __name__ == "__main__":
    main()
