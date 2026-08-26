"""
Central path constants for the professor data collection pipeline.

Everything the pipeline reads or writes lives under a handful of well-known
directories.  Keeping them here means no collector ever has to guess where
the dataset, cache or fixture files are.
"""

import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATASETS_DIR = os.path.join(PROJECT_ROOT, 'datasets')
SCHOLARS_DIR = os.path.join(DATASETS_DIR, 'scholars')
FACULTY_DIR = os.path.join(DATASETS_DIR, 'faculty')

UNIFIED_DIR = os.path.join(DATASETS_DIR, 'unified')
CACHE_DIR = os.path.join(DATASETS_DIR, 'cache')
RANKINGS_DIR = os.path.join(DATASETS_DIR, 'rankings')

HTML_PAGES_DIR = os.path.join(PROJECT_ROOT, 'html_pages')

PROFESSOR_MASTER_CSV = os.path.join(UNIFIED_DIR, 'professor_master.csv')
PUBLICATIONS_CSV = os.path.join(UNIFIED_DIR, 'publications.csv')
RANKINGS_CSV = os.path.join(RANKINGS_DIR, 'carnegie_rankings.csv')

ALL_DIRS = [UNIFIED_DIR, CACHE_DIR, RANKINGS_DIR]


def ensure_dirs() -> None:
    for d in ALL_DIRS:
        os.makedirs(d, exist_ok=True)
