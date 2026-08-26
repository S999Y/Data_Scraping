"""Research area classification from scraped labels and publication topics."""

UNKNOWN_AREA = "Other"


def classify(text, target_areas, multi=True):
    """Return matching target areas from text.

    When ``multi=True`` (default), returns all areas with at least one keyword
    match, joined by ``;``.  When ``multi=False``, returns only the single best
    area (old behaviour).  Returns ``UNKNOWN_AREA`` when nothing matches.
    """
    if not text:
        return UNKNOWN_AREA
    low = text.lower()
    if multi:
        matched = []
        for area, keywords in target_areas.items():
            if any(kw in low for kw in keywords):
                matched.append(area)
        return ";".join(matched) if matched else UNKNOWN_AREA

    best_area = UNKNOWN_AREA
    best_score = 0
    for area, keywords in target_areas.items():
        score = sum(1 for kw in keywords if kw in low)
        if score > best_score:
            best_score = score
            best_area = area
    return best_area
