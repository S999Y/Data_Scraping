"""
test_scraper - a modular, reusable professor data collection pipeline.

Phase 1 collects data only (no model, no new installs).  It merges free
academic APIs (OpenAlex, ORCID, Crossref, DBLP, Semantic Scholar) with the
existing Google Scholar / faculty-page scrapers into two unified datasets:

    datasets/unified/professor_master.csv   one row per professor
    datasets/unified/publications.csv       one row per paper
"""

from ._paths import ensure_dirs  # noqa: F401

__version__ = '0.1.0'
