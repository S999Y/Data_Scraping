"""Derived scoring: is_pickable, matched venues, target pub counts."""

from .research_area import classify, UNKNOWN_AREA
from publishers.openalex import venue_matches


def build_row(university, rank, profile, enrichment, cfg):
    """Combine scraped profile + OpenAlex enrichment into one output row.

    When ``enrichment`` is None (scrape-only mode) the OpenAlex-derived columns
    are left blank and ``is_pickable`` is left empty rather than guessed.
    """
    research_text = " ".join(
        part for part in (profile.get("research_text", ""), " ".join((enrichment or {}).get("topics", []))) if part
    )
    research_area = classify(research_text, cfg["target_areas"])

    matched_short, matched_sources = [], []
    n_target_pubs, total_pubs = 0, 0
    is_pickable = ""
    if enrichment is not None:
        sources = enrichment.get("sources", [])
        matched_short, matched_sources = venue_matches(sources, cfg["target_venues"])
        n_target_pubs = len(matched_sources)
        total_pubs = enrichment.get("n_works_fetched", 0)

        pick_cfg = cfg["is_pickable"]
        is_pickable = True
        if pick_cfg.get("require_rank_r1"):
            is_pickable = is_pickable and rank == "r1"
        if pick_cfg.get("exclude_other_area"):
            areas = [a.strip() for a in research_area.split(";")]
            is_pickable = is_pickable and any(a != UNKNOWN_AREA for a in areas)
        min_pubs = pick_cfg.get("min_target_pubs")
        if min_pubs is not None:
            is_pickable = is_pickable and n_target_pubs >= min_pubs
        is_pickable = "TRUE" if is_pickable else "FALSE"

    email = profile.get("email", "")
    return {
        "University": university,
        "Rank": rank,
        "Professor name": profile.get("name", ""),
        "Title": profile.get("title", ""),
        "Email": email,
        "Mail": email,
        "Lab link": profile.get("lab_url", ""),
        "Research area": research_area,
        "is_pickable": is_pickable,
        "Matched_venues": ";".join(matched_short),
        "N_target_pubs": n_target_pubs,
        "Total_publications": total_pubs,
        "profile_url": profile.get("profile_url", ""),
    }
