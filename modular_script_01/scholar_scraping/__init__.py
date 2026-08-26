"""
Scholar Scraping Package

Single-config scraper for Google Scholar profile pages. Fully loads the
entire publication list ("Show more") before extracting every data point.
"""

from .config import SCHOLAR_CONFIG
from .scraper import ScholarScraper

__version__ = "1.0.0"
__all__ = ['SCHOLAR_CONFIG', 'ScholarScraper']
