"""
run_demo.py - Single entry point for the Automatic Scraping project demo.

Usage:
    python run_demo.py selftest                              # Offline validation (no network)
    python run_demo.py scrape --offline                      # Parse saved HTML pages
    python run_demo.py scrape --live --sites mit_eecs berkeley  # Live scrape specific sites
    python run_demo.py scrape --live                         # Live scrape all sites
    python run_demo.py single --name "Regina Barzilay"       # 7-API pipeline on one professor
    python run_demo.py batch --limit 5                       # Batch process professors from CSVs
    python run_demo.py full --limit 2                        # End-to-end: scrape + API enrich

Prerequisites:
    pip install -r requirements.txt

This script demonstrates the two main components of our project:
  1. University Faculty Web Scraping - scrapes CS faculty from 83 university websites
  2. 7-API Data Pipeline - enriches professor data using 7 free academic APIs
"""

import argparse
import os
import sys
import time

# Ensure we are running from the final_code directory
FINAL_CODE_DIR = os.path.dirname(os.path.abspath(__file__))
if FINAL_CODE_DIR not in sys.path:
    sys.path.insert(0, FINAL_CODE_DIR)


def load_api_key():
    """Load the first available OpenAlex API key from datasets/api/api_key.txt."""
    key_path = os.path.join(FINAL_CODE_DIR, 'datasets', 'api', 'api_key.txt')
    if not os.path.exists(key_path):
        return None
    try:
        with open(key_path, 'r') as f:
            keys = [line.strip() for line in f if line.strip()]
        if keys:
            return keys[0]
    except Exception:
        pass
    return None


API_KEY = load_api_key()


# ============================================================================
# SECTION 1: University Web Scraping Demo
# ============================================================================

def demo_scrape_offline():
    """Demo: Parse saved HTML pages from university websites (no network needed)."""
    print('=' * 70)
    print('DEMO 1: University Faculty Web Scraping (Offline Mode)')
    print('=' * 70)
    print()
    print('This demo parses pre-saved HTML pages from university CS faculty')
    print('listing pages using our custom per-university adapters.')
    print()

    from bs4 import BeautifulSoup
    import csv
    from pathlib import Path

    html_dir = Path(FINAL_CODE_DIR) / 'html_pages'

    # Try to find HTML pages
    html_files = []
    if html_dir.exists():
        for f in html_dir.rglob('*.html'):
            if 'scholar' not in f.name.lower():
                html_files.append(f)

    if not html_files:
        print('  No saved HTML pages found in html_pages/')
        print('  Run with --live mode to scrape real websites instead.')
        return

    # Import the adapters
    from adapters import (parse_mit_eecs, parse_berkeley, parse_stanford,
                          parse_cmu_csd, parse_generic)
    from driver import extract_name_links

    # Map filenames to parsers
    parser_map = {
        'mit_eecs': parse_mit_eecs,
        'berkeley': parse_berkeley,
        'stanford': parse_stanford,
        'cmu_csd': parse_cmu_csd,
    }

    for html_file in html_files[:4]:  # Show first 4
        slug = html_file.stem
        if slug.endswith('.rendered'):
            slug = slug.replace('.rendered', '')

        parser = parser_map.get(slug, parse_generic)
        parser_name = parser.__name__

        print(f'\n  --- Parsing: {html_file.name} (parser: {parser_name}) ---')

        try:
            text = html_file.read_text(encoding='utf-8', errors='ignore')
            soup = BeautifulSoup(text, 'html.parser')
            rows = parser(soup, f'https://example.edu/{slug}')

            if not rows and parser is parse_generic:
                rows = extract_name_links(soup, f'https://example.edu/{slug}')

            print(f'  Found {len(rows)} faculty members:')
            for r in rows[:5]:
                name = r.get('name', 'N/A')
                email = r.get('email', '')
                email_str = f' | {email}' if email else ''
                print(f'    - {name}{email_str}')
            if len(rows) > 5:
                print(f'    ... and {len(rows) - 5} more')

        except Exception as e:
            print(f'  Error parsing {html_file.name}: {e}')

    print()
    print('  This demonstrates how our 40+ custom parsers extract structured')
    print('  faculty data from different university website layouts.')


def demo_scrape_live(sites=None):
    """Demo: Live scrape university faculty pages."""
    print('=' * 70)
    print('DEMO 1B: University Faculty Web Scraping (Live Mode)')
    print('=' * 70)
    print()
    print('This demo scrapes real university CS faculty pages from the web.')
    print()

    try:
        from driver import scrape_site, SLUG_TO_UNIV, FINAL_COLUMNS
        import driver
    except ImportError as e:
        print(f'  Error importing driver: {e}')
        return

    import csv
    from pathlib import Path

    # Pick sites to scrape
    if sites:
        target_sites = sites
    else:
        # Demo with a few well-known universities
        target_sites = ['mit_eecs', 'berkeley', 'ucsd']

    out_dir = Path(FINAL_CODE_DIR) / 'datasets' / 'faculty'
    out_dir.mkdir(parents=True, exist_ok=True)

    all_rows = []
    for slug in target_sites:
        if slug not in SLUG_TO_UNIV:
            print(f'  Unknown site: {slug} (available: {", ".join(sorted(SLUG_TO_UNIV.keys())[:10])}...)')
            continue

        univ_name = SLUG_TO_UNIV[slug]
        # Find the URL from universities.py
        import universities
        univ_data = None
        for u in universities.UNIVERSITIES:
            if u['name'] == univ_name:
                univ_data = u
                break

        if not univ_data:
            print(f'  No URL found for {univ_name}')
            continue

        print(f'\n  Scraping: {univ_name} ...')
        try:
            rows, status = scrape_site(slug, univ_data['faculty_url'])
            print(f'  Result: {len(rows)} faculty found (status: {status})')

            for r in rows[:3]:
                print(f'    - {r["name"]} | {r.get("email", "")}')
            if len(rows) > 3:
                print(f'    ... and {len(rows) - 3} more')

            # Save per-university CSV
            for r in rows:
                all_rows.append({
                    'University': univ_name,
                    'R': univ_data['r'],
                    'Ranking': univ_data['ranking'],
                    'Professor name': r['name'],
                    'Email': r['email'],
                    'Mail': r['mail'],
                    'Lab link': r['lab_link'],
                    'Research area': r['research'],
                })

            # Write individual CSV
            csv_path = out_dir / f'{slug}_faculty.csv'
            with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=FINAL_COLUMNS)
                writer.writeheader()
                writer.writerows([row for row in all_rows
                                  if row['University'] == univ_name])
            print(f'  Saved -> {csv_path.name}')

            time.sleep(1)  # Be polite

        except Exception as e:
            print(f'  Error scraping {univ_name}: {e}')

    if all_rows:
        combined_path = out_dir / 'demo_combined_faculty.csv'
        with open(combined_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=FINAL_COLUMNS)
            writer.writeheader()
            writer.writerows(all_rows)
        print(f'\n  Combined output: {len(all_rows)} rows -> {combined_path.name}')

    print()
    print('  Our scraper handles different website layouts using 40+')
    print('  custom per-university adapters, plus a generic fallback.')


# ============================================================================
# SECTION 2: 7-API Data Pipeline Demo
# ============================================================================

def demo_single_professor(name='Regina Barzilay'):
    """Demo: Run the 7-API pipeline on a single professor."""
    print('=' * 70)
    print('DEMO 2: 7-API Data Pipeline (Single Professor)')
    print('=' * 70)
    print()
    print('This demo collects data for one professor from 7 free academic APIs:')
    print('  1. OpenAlex   - Author search, citations, h-index, topics')
    print('  2. ORCID      - Bio, website, external identifiers')
    print('  3. Crossref   - Paper details, DOI, venue, year')
    print('  4. DBLP       - CS publication list')
    print('  5. Semantic Scholar - Metrics, affiliations, interests')
    print('  6. Google Scholar  - Full profile + all papers')
    print('  7. Faculty Pages   - University listing data')
    print()
    print(f'  Target professor: {name}')
    print()

    try:
        from test_scraper.pipeline import collect_professor, save_professor
        from test_scraper.test import print_report
    except ImportError as e:
        print(f'  Error importing pipeline: {e}')
        return

    # Use only the free API sources (no scholar/faculty URL needed for demo)
    sources = ['openalex', 'orcid', 'crossref', 'dblp', 'semantic']

    print('  Collecting data from APIs...')
    if API_KEY:
        print(f'  Using OpenAlex API key: {API_KEY[:8]}...')
    print()

    start = time.time()
    try:
        merged = collect_professor(
            name=name,
            sources=sources,
            use_cache=True,
            delay=0.3,
            api_key=API_KEY,
        )
        elapsed = time.time() - start

        # Save the result
        from test_scraper._paths import ensure_dirs
        ensure_dirs()
        save_professor(merged)

        # Print the report
        print_report(merged)
        print(f'  Time: {elapsed:.1f}s')
        print()

        # Show some publication samples
        pubs = merged.get('publications') or []
        if pubs:
            print(f'  Sample publications ({len(pubs)} total):')
            for p in pubs[:5]:
                year = p.get('year', '?')
                title = (p.get('title') or 'Untitled')[:70]
                venue = (p.get('venue') or '')[:30]
                print(f'    [{year}] {title}')
                if venue:
                    print(f'           Venue: {venue}')

    except Exception as e:
        print(f'  Error: {e}')
        import traceback
        traceback.print_exc()

    print()
    print('  The pipeline merges data from multiple sources, deduplicates')
    print('  publications, infers research topics, and saves unified CSVs.')


def demo_batch(limit=5):
    """Demo: Batch process multiple professors."""
    print('=' * 70)
    print('DEMO 3: 7-API Data Pipeline (Batch Mode)')
    print('=' * 70)
    print()
    print('This demo processes multiple professors from our scraped faculty CSVs.')
    print()

    try:
        from test_scraper.test import SETTINGS
        from test_scraper.pipeline import batch_from_datasets, run_pipeline
    except ImportError as e:
        print(f'  Error importing pipeline: {e}')
        return

    print('  Building input list from datasets/faculty/*.csv ...')
    inputs = batch_from_datasets(
        scholar_limit=0,
        faculty_limit=limit or 5,
    )

    if not inputs:
        print('  No professors found in datasets/faculty/')
        print('  Run "python run_demo.py scrape" first to generate faculty CSVs.')
        return

    inputs = inputs[:limit or 5]
    print(f'  Found {len(inputs)} professors to process')
    print()

    # Use free API sources only for demo (avoid Google Scholar rate limits)
    sources = ['openalex', 'semantic']

    print(f'  Running pipeline with sources: {sources}')
    print()

    start = time.time()
    try:
        results = run_pipeline(
            inputs,
            sources=sources,
            use_cache=True,
            delay=0.5,
            verbose=True,
            api_key=API_KEY,
        )
        elapsed = time.time() - start
        print(f'\n  Batch complete: {len(results)} professors in {elapsed:.1f}s')

    except Exception as e:
        print(f'  Error: {e}')
        import traceback
        traceback.print_exc()

    print()
    print('  Our batch pipeline processes professors from our scraped data,')
    print('  enriching each one with metrics from multiple academic APIs.')


def demo_selftest():
    """Demo: Run the offline selftest."""
    print('=' * 70)
    print('DEMO: Offline Self-Test (No Network Required)')
    print('=' * 70)
    print()
    print('This validates the entire pipeline using saved HTML fixtures.')
    print()

    try:
        from test_scraper.test import run_selftest
        success = run_selftest()
        if success:
            print()
            print('  All pipeline components validated successfully!')
        else:
            print()
            print('  Selftest reported issues (see above).')
    except Exception as e:
        print(f'  Error during selftest: {e}')
        import traceback
        traceback.print_exc()

        # Try partial selftest
        print()
        print('  Attempting partial validation...')
        try:
            from test_scraper.rankings import lookup_rank
            from test_scraper.topics import infer_topics

            print('  1) Topic inference...')
            topics = infer_topics(['machine learning', 'deep learning', 'computer vision'])
            print(f'     OK - topics: {topics}')

            print('  2) University rank lookup...')
            rank = lookup_rank('Massachusetts Institute of Technology')
            print(f'     OK - MIT -> {rank}')

            print('  Partial validation passed!')
        except Exception as e2:
            print(f'  Partial validation also failed: {e2}')


# ============================================================================
# SECTION 3: Full Pipeline Demo
# ============================================================================

def demo_full(limit=2):
    """Demo: End-to-end pipeline (scrape + API enrich + output)."""
    print('=' * 70)
    print('DEMO 4: Full Pipeline (Scrape -> API Enrich -> Output)')
    print('=' * 70)
    print()
    print('This demo shows the complete workflow:')
    print('  1. Scrape faculty from university websites')
    print('  2. Enrich each professor with API data')
    print('  3. Generate unified output CSVs')
    print()

    # Step 1: Scrape
    print('--- Step 1: Scraping Faculty ---')
    try:
        from driver import scrape_site, SLUG_TO_UNIV, FINAL_COLUMNS
        import universities
        import csv
        from pathlib import Path

        demo_sites = ['mit_eecs', 'ucsd'][:limit]
        out_dir = Path(FINAL_CODE_DIR) / 'datasets' / 'faculty'
        out_dir.mkdir(parents=True, exist_ok=True)

        scraped_names = []
        for slug in demo_sites:
            if slug not in SLUG_TO_UNIV:
                continue
            univ_name = SLUG_TO_UNIV[slug]
            univ_data = next((u for u in universities.UNIVERSITIES
                              if u['name'] == univ_name), None)
            if not univ_data:
                continue

            print(f'  Scraping {univ_name}...')
            rows, status = scrape_site(slug, univ_data['faculty_url'])
            print(f'  -> {len(rows)} faculty found')

            # Save CSV
            csv_rows = [{
                'University': univ_name, 'R': univ_data['r'],
                'Ranking': univ_data['ranking'],
                'Professor name': r['name'], 'Email': r['email'],
                'Mail': r['mail'], 'Lab link': r['lab_link'],
                'Research area': r['research'],
            } for r in rows]
            csv_path = out_dir / f'{slug}_faculty.csv'
            with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
                w = csv.DictWriter(f, fieldnames=FINAL_COLUMNS)
                w.writeheader()
                w.writerows(csv_rows)

            scraped_names.extend(r['name'] for r in rows[:limit])
            time.sleep(1)

    except Exception as e:
        print(f'  Scraping error: {e}')
        scraped_names = []

    # Step 2: API Enrich
    print()
    print('--- Step 2: API Enrichment ---')

    if not scraped_names:
        # Fallback: use a hardcoded demo name
        scraped_names = ['Regina Barzilay', 'Geoffrey Hinton'][:limit]
        print(f'  Using demo professors: {", ".join(scraped_names)}')

    try:
        from test_scraper.pipeline import collect_professor, save_professor
        from test_scraper._paths import ensure_dirs
        ensure_dirs()

        for name in scraped_names[:limit]:
            print(f'  Enriching: {name}...')
            merged = collect_professor(
                name=name,
                sources=['openalex', 'orcid', 'crossref', 'dblp', 'semantic'],
                use_cache=True,
                delay=0.3,
                api_key=API_KEY,
            )
            save_professor(merged)
            pubs = len(merged.get('publications') or [])
            rank = merged.get('rank') or 'n/a'
            print(f'    -> rank={rank} | publications={pubs} | '
                  f'h-index={merged.get("h_index", "n/a")}')

    except Exception as e:
        print(f'  API enrichment error: {e}')

    # Step 3: Show output
    print()
    print('--- Step 3: Output Files ---')
    from test_scraper._paths import PROFESSOR_MASTER_CSV, PUBLICATIONS_CSV
    for path in [PROFESSOR_MASTER_CSV, PUBLICATIONS_CSV]:
        if os.path.exists(path):
            import pandas as pd
            try:
                df = pd.read_csv(path, dtype=str)
                print(f'  {os.path.basename(path)}: {len(df)} rows')
            except Exception:
                print(f'  {os.path.basename(path)}: exists (could not read)')
        else:
            print(f'  {os.path.basename(path)}: not yet created')

    print()
    print('  The full pipeline demonstrates our automated scraping and')
    print('  data enrichment system from start to finish.')


# ============================================================================
# CLI Entry Point
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Automatic Scraping Project - Demo Runner',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_demo.py selftest                              # Offline validation
  python run_demo.py scrape --offline                      # Parse saved HTML
  python run_demo.py scrape --live --sites mit_eecs        # Live scrape MIT
  python run_demo.py single --name "Regina Barzilay"       # 7-API on one prof
  python run_demo.py batch --limit 3                       # Batch 3 professors
  python run_demo.py full --limit 2                        # Full pipeline demo
        """)

    subparsers = parser.add_subparsers(dest='command', help='Demo command')

    # selftest
    subparsers.add_parser('selftest', help='Offline validation (no network)')

    # scrape
    scrape_parser = subparsers.add_parser('scrape', help='Scrape university faculty pages')
    scrape_mode = scrape_parser.add_mutually_exclusive_group(required=True)
    scrape_mode.add_argument('--offline', action='store_true',
                             help='Parse saved HTML pages (no network)')
    scrape_mode.add_argument('--live', action='store_true',
                             help='Live scrape from university websites')
    scrape_parser.add_argument('--sites', nargs='*',
                               help='Specific site slugs (e.g., mit_eecs berkeley)')

    # single
    single_parser = subparsers.add_parser('single', help='7-API pipeline on one professor')
    single_parser.add_argument('--name', default='Regina Barzilay',
                               help='Professor name (default: Regina Barzilay)')

    # batch
    batch_parser = subparsers.add_parser('batch', help='Batch process from CSVs')
    batch_parser.add_argument('--limit', type=int, default=5,
                              help='Max professors to process (default: 5)')

    # full
    full_parser = subparsers.add_parser('full', help='Full pipeline demo')
    full_parser.add_argument('--limit', type=int, default=2,
                             help='Max professors per step (default: 2)')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        print()
        print('Quick start: python run_demo.py selftest')
        return

    print()
    print('============================================================')
    print('  AUTOMATIC SCRAPING PROJECT - LIVE DEMO')
    print('  University Faculty Scraping + 7-API Data Pipeline')
    print('============================================================')
    print()

    if args.command == 'selftest':
        demo_selftest()
    elif args.command == 'scrape':
        if args.offline:
            demo_scrape_offline()
        else:
            demo_scrape_live(sites=args.sites)
    elif args.command == 'single':
        demo_single_professor(name=args.name)
    elif args.command == 'batch':
        demo_batch(limit=args.limit)
    elif args.command == 'full':
        demo_full(limit=args.limit)

    print()
    print('============================================================')
    print('  Demo complete!')
    print('============================================================')


if __name__ == '__main__':
    main()
