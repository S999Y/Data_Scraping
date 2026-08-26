"""
Source registry - maps source names to collector classes and builds the
collector instances used by the pipeline.

Supported sources:
    openalex, orcid, crossref, dblp, semantic, scholar, faculty
"""

from .collectors import COLLECTORS
from .collectors.base import BaseCollector

DEFAULT_SOURCES = ['openalex', 'orcid', 'crossref', 'dblp', 'semantic',
                   'scholar', 'faculty']

# Priority for conflicting profile fields: earlier = wins.
SOURCE_PRIORITY = ['scholar', 'openalex', 'semantic', 'dblp', 'crossref',
                   'orcid', 'faculty']


class SourceRegistry:
    def __init__(self, names=None, **collector_kwargs):
        names = names or DEFAULT_SOURCES
        self.names = [n for n in names if n in COLLECTORS]
        self.kwargs = collector_kwargs
        self._instances = {}

    def instance(self, name: str) -> BaseCollector:
        if name not in self._instances:
            cls = COLLECTORS[name]
            self._instances[name] = cls(**self.kwargs)
        return self._instances[name]

    def active(self):
        for name in self.names:
            yield self.instance(name)

    def __iter__(self):
        return iter(self.names)

    def __len__(self):
        return len(self.names)


def build_registry(names=None, **kwargs) -> SourceRegistry:
    return SourceRegistry(names=names, **kwargs)
