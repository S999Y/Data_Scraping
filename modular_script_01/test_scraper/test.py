"""
test_scraper - user-facing entry point.

No command-line arguments needed.  Just import the functions and call them:

    from test_scraper.test import scrape_professor, collect_names, run_batch, run_selftest

    run_selftest()                              # offline check (no network)
    scrape_professor('Regina Barzilay')         # one professor (live)
    collect_names(['Geoffrey Hinton', 'Yann LeCun'])
    run_batch(limit=5)                          # from datasets/scholars + faculty
"""

import os
import sys

from ._paths import HTML_PAGES_DIR, PROFESSOR_MASTER_CSV, PUBLICATIONS_CSV
from .pipeline import batch_from_datasets, collect_professor, save_professor

# ============================================================================
# SETTINGS
# ============================================================================

SETTINGS = {
    # Single-professor mode
    'PROFESSOR_NAME': 'Regina Barzilay',

    # Which sources to use (subset of: openalex, orcid, crossref, dblp,
    # semantic, scholar, faculty).  Use all free APIs plus your scrapers:
    'SOURCES': ['openalex', 'orcid', 'crossref', 'dblp', 'semantic',
                'scholar', 'faculty'],

    # Google Scholar profile page (live).  Leave SCHOLAR_HTML empty to use it.
    'SCHOLAR_URL': 'https://scholar.google.com/citations?hl=en&user=6jv2-OYAAAAJ&view_op=list_works',
    # Offline Google Scholar fixture (html_pages/scholar.html).  Set this to
    # skip the live scholar load, e.g. for testing:
    #   'SCHOLAR_HTML': os.path.join(HTML_PAGES_DIR, 'scholar.html')
    'SCHOLAR_HTML': None,

    # Faculty listing page + its registered config key (optional).
    'FACULTY_URL': None,
    'FACULTY_CONFIG': 'mit_profed_config',

    # Batch mode
    'BATCH_LIMIT': 5,            # None = everything
    'BATCH_SCHOLAR_LIMIT': 3,
    'BATCH_FACULTY_LIMIT': 5,

    # Behaviour
    'USE_CACHE': True,
    'DELAY': 0.3,                # seconds between requests
}

# ============================================================================
# High-level actions
# ============================================================================

NAME_SOURCES = ['openalex', 'orcid', 'crossref', 'dblp', 'semantic']


def scrape_professor(name=None, sources=None, scholar_url=None,
                     scholar_html=None, faculty_url=None,
                     faculty_config=None, use_cache=None, delay=None,
                     verbose=True):
    """Collect one professor and save them to the unified datasets.

    Examples:
        scrape_professor('Regina Barzilay')
        scrape_professor('Regina Barzilay', sources=['openalex', 'semantic'])
        scrape_professor('Regina Barzilay', scholar_html=r'html_pages/scholar.html')
    """
    cfg = SETTINGS
    kwargs = dict(
        name=name or cfg['PROFESSOR_NAME'],
        sources=sources or cfg['SOURCES'],
        scholar_url=scholar_url or cfg['SCHOLAR_URL'],
        html_path=scholar_html if scholar_html is not None else cfg['SCHOLAR_HTML'],
        faculty_url=faculty_url if faculty_url is not None else cfg['FACULTY_URL'],
        faculty_config=faculty_config or cfg['FACULTY_CONFIG'],
        use_cache=cfg['USE_CACHE'] if use_cache is None else use_cache,
        delay=cfg['DELAY'] if delay is None else delay,
    )
    merged = collect_professor(**kwargs)
    save_professor(merged)
    if verbose:
        print_report(merged)
    return merged


def collect_names(names, sources=None, use_cache=None, delay=None, verbose=True):
    """Collect a list of professor names and save them all.

    Uses the API-only sources by default (scholar/faculty need URLs); pass
    `sources` to include them.

    Examples:
        collect_names(['Geoffrey Hinton', 'Yann LeCun'])
        collect_names(['Regina Barzilay'], sources=['openalex', 'scholar'])
    """
    from .pipeline import run_pipeline

    cfg = SETTINGS
    inputs = [{'name': str(n).strip()} for n in names if str(n).strip()]
    if not inputs:
        print('No names provided.')
        return []
    return run_pipeline(
        inputs,
        sources=sources or NAME_SOURCES,
        use_cache=cfg['USE_CACHE'] if use_cache is None else use_cache,
        delay=cfg['DELAY'] if delay is None else delay,
        verbose=verbose)


def run_batch(limit=None, scholar_limit=None, faculty_limit=None,
              use_cache=None, delay=None):
    """Collect professors from datasets/scholars/*.csv and datasets/faculty/*.csv.

    Examples:
        run_batch()                      # uses SETTINGS limits
        run_batch(limit=10)
        run_batch(scholar_limit=2, faculty_limit=5)
    """
    from .pipeline import run_pipeline

    cfg = SETTINGS
    inputs = batch_from_datasets(
        scholar_limit=cfg['BATCH_SCHOLAR_LIMIT'] if scholar_limit is None else scholar_limit,
        faculty_limit=cfg['BATCH_FACULTY_LIMIT'] if faculty_limit is None else faculty_limit)
    if limit:
        inputs = inputs[:limit]
    if not inputs:
        print('No professors found in datasets/scholars or datasets/faculty.')
        return []
    print(f'Batch running for {len(inputs)} professors...')
    return run_pipeline(
        inputs,
        use_cache=cfg['USE_CACHE'] if use_cache is None else use_cache,
        delay=cfg['DELAY'] if delay is None else delay)


def run_selftest():
    """Offline check of the whole pipeline (no network needed)."""
    from .collectors.scholar import ScholarCollector
    from .rankings import build_rankings_csv, lookup_rank
    from .topics import infer_topics

    print('=== test_scraper selftest ===')

    fixture = os.path.join(HTML_PAGES_DIR, 'scholar.html')
    if not os.path.exists(fixture):
        print(f'FAIL: fixture not found: {fixture}')
        return False

    print(f'1) Offline scholar load from {fixture}')
    collector = ScholarCollector()
    result = collector.collect(name='Regina Barzilay', html_path=fixture)
    pubs = result.get('publications') or []
    assert pubs, 'no publications extracted'
    print(f'   OK  publications={len(pubs)} name={result.get("name")} '
          f'h_index={result.get("h_index")}')

    print('2) Topic inference')
    topics = infer_topics([result.get('name'), 'machine learning', 'nlp', 'bioinformatics'])
    print(f'   OK  topics={topics}')
    assert topics, 'no topics inferred'

    print('3) University rank lookup (fallback map)')
    rank = lookup_rank('Massachusetts Institute of Technology')
    print(f'   OK  MIT -> {rank}')
    assert rank == 'R1', f'expected R1, got {rank}'

    print('4) Merge + save via collect_professor (offline scholar only)')
    merged = collect_professor(
        name='Regina Barzilay',
        sources=['scholar'],
        html_path=fixture,
        use_cache=False)
    assert len(merged.get('publications') or []), 'publications lost'
    assert merged.get('name'), 'name missing'
    assert merged.get('research_topics'), 'research_topics missing'
    save_professor(merged)
    print(f'   OK  merged publications={len(merged["publications"])} '
          f'topics={merged["research_topics"]}')
    print(f'   saved -> {PROFESSOR_MASTER_CSV}')
    print(f'          -> {PUBLICATIONS_CSV}')

    print('5) Rankings CSV build (live fetch, best-effort)')
    try:
        build_rankings_csv()
        print('   OK  carnegie_rankings.csv written')
    except Exception as e:
        print(f'   WARN ranking fetch failed (skipping): {e}')

    print('=== selftest passed ===')
    return True


def print_report(merged):
    print(f'Professor : {merged.get("name")}')
    print(f'University: {merged.get("university") or "n/a"} '
          f'({merged.get("rank") or "n/a"})')
    print(f'Sources   : {", ".join(merged.get("sources") or [])}')
    print(f'Citations : {merged.get("total_citations")} | '
          f'h-index: {merged.get("h_index")} | '
          f'i10: {merged.get("i10_index")}')
    print(f'Papers    : {len(merged.get("publications") or [])}')
    print(f'Topics    : {"; ".join(merged.get("research_topics") or []) or "none"}')
    print(f'Output    : {PROFESSOR_MASTER_CSV}')
    print(f'          : {PUBLICATIONS_CSV}')


# ============================================================================
# CLI
# ============================================================================

def main(argv=None):
    argv = argv or sys.argv[1:]
    if not argv:
        action = 'single'
    else:
        action = argv[0].lower()

    if action in ('selftest', 'self'):
        return run_selftest()
    if action in ('batch', 'b'):
        return run_batch(SETTINGS.get('BATCH_LIMIT'))
    if action in ('single', 's'):
        return scrape_professor()
    print(f'Unknown action: {action}')
    print('Usage: python -m test_scraper.test [selftest|single|batch]')
    return None


if __name__ == '__main__':
    main()
