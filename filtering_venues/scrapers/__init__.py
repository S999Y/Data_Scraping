"""School registry: university name -> (scraper factory, OpenAlex ROR id).

The pipeline now drives every university from data/university_data.json. Custom
scrapers exist for a few schools; all others use the config-driven
``GenericScraper`` (config in data/school_config.json).
"""

from .base import BaseScraper
from .cmu import CMUScraper
from .generic import GenericScraper
from .mit import MITScraper
from .stanford import StanfordScraper
from .tnstate import TennesseeStateScraper
from .ucla import UCLAScraper
from .umkc import UMKcScraper
from .wright import WrightStateScraper

CUSTOM_SCRAPERS = {
    "Massachusetts Institute of Technology": MITScraper,
    "Carnegie Mellon University": CMUScraper,
    "Stanford University": StanfordScraper,
    "Wright State University": WrightStateScraper,
    "Tennessee State University": TennesseeStateScraper,
    "University of Missouri\u2013Kansas City": UMKcScraper,
    "University of California, Los Angeles (UCLA)": UCLAScraper,
}

ROR_MAP = {
    "Massachusetts Institute of Technology": "https://ror.org/042nb2s44",
    "Carnegie Mellon University": "https://ror.org/05x2bcf33",
    "Stanford University": "https://ror.org/00f54p054",
}


def make_scraper(university, rank, faculty_url, config=None, delay=0.5):
    """Return a scraper instance for a university (custom or generic)."""
    cls = CUSTOM_SCRAPERS.get(university, GenericScraper)
    kwargs = {"university": university, "rank": rank, "faculty_url": faculty_url, "delay": delay}
    if cls is GenericScraper:
        kwargs["config"] = config or {}
    return cls(**kwargs)


__all__ = ["BaseScraper", "MITScraper", "CMUScraper", "StanfordScraper", "GenericScraper", "make_scraper"]
