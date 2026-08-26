"""Data collectors - one module per remote source."""

from .base import BaseCollector  # noqa: F401
from .crossref import CrossrefCollector  # noqa: F401
from .dblp import DblpCollector  # noqa: F401
from .faculty import FacultyCollector  # noqa: F401
from .openalex import OpenAlexCollector  # noqa: F401
from .orcid import OrcidCollector  # noqa: F401
from .scholar import ScholarCollector  # noqa: F401
from .semantic import SemanticScholarCollector  # noqa: F401

COLLECTORS = {
    'openalex': OpenAlexCollector,
    'orcid': OrcidCollector,
    'crossref': CrossrefCollector,
    'dblp': DblpCollector,
    'semantic': SemanticScholarCollector,
    'scholar': ScholarCollector,
    'faculty': FacultyCollector,
}

__all__ = ['BaseCollector', 'COLLECTORS']
