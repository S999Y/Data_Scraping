"""Merge all CSVs in data/ into one file, keeping only professors whose
research area is related to AI / Machine Learning / NLP / Computer Vision.

Usage:
    python merge_ai_professors.py [input_dir] [output_path]
"""

import glob
import os
import re
import sys

import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_PATH = os.path.join(BASE_DIR, "merged_ai_professors.csv")
RANKING_2026_PATH = os.path.join(DATA_DIR, "ranking_2026.csv")

# Common output columns (lowercase, underscore). 'rank' is the r1/r2 tier;
# 'ranking' is the numeric university rank.
OUTPUT_COLUMNS = [
    "university",
    "rank",
    "ranking",
    "professor_name",
    "title",
    "email",
    "mail",
    "lab_link",
    "research_area",
    "is_pickable",
    "matched_venues",
    "n_target_pubs",
    "total_publications",
    "profile_url",
]

# Map the original source column names to the normalized output names.
INPUT_COLUMN_MAP = {
    "University": "university",
    "Rank": "rank",
    "Ranking": "ranking",
    "Professor name": "professor_name",
    "Title": "title",
    "Email": "email",
    "Mail": "mail",
    "Lab link": "lab_link",
    "Research area": "research_area",
    "is_pickable": "is_pickable",
    "Matched_venues": "matched_venues",
    "N_target_pubs": "n_target_pubs",
    "Total_publications": "total_publications",
    "profile_url": "profile_url",
}

# Terms (case-insensitive regex) that mark a research area as AI/ML/NLP/CV related.
AI_KEYWORDS = [
    r"\bai\b",
    r"artificial intelligence",
    r"machine learning",
    r"deep learning",
    r"reinforcement learning",
    r"\bnlp\b",
    r"natural language",
    r"computer vision",
    r"\bvision\b",
    r"image processing",
    r"image analysis",
    r"medical imaging",
    r"\bneural\b",
    r"\bneuroai\b",
    r"pattern recognition",
    r"generative",
    r"\bintelligent\b",
    r"\bspeech\b",
    r"\bcv\b",
]

AI_KEYWORDS_RE = re.compile("|".join(f"(?:{k})" for k in AI_KEYWORDS), re.IGNORECASE)

# Research areas exactly equal to these (case-insensitive) are always excluded.
AI_EXCLUDE = {
    "other",
}


def is_ai_related(value: str) -> bool:
    """Return True if the research area text matches an AI/ML/NLP/CV keyword."""
    if not value:
        return False
    value = str(value).strip()
    if value.lower() in AI_EXCLUDE:
        return False
    return bool(AI_KEYWORDS_RE.search(value))


def _completeness(row: pd.Series) -> int:
    """Score how much useful info a row carries (used for duplicate preference)."""
    score = 0
    for col in ("title", "research_area", "is_pickable", "matched_venues",
                "n_target_pubs", "total_publications", "profile_url"):
        val = row.get(col)
        if isinstance(val, str) and val.strip():
            score += 1
    return score


def load_and_normalize(path: str) -> pd.DataFrame:
    """Read a CSV and bring it to the common OUTPUT_COLUMNS schema."""
    df = pd.read_csv(path, dtype=str).fillna("")
    df.columns = [str(c).strip() for c in df.columns]
    df = df.rename(columns=INPUT_COLUMN_MAP)

    for col in OUTPUT_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    # combined_faculty.csv uses 'R' for the tier and 'Ranking' for the numeric rank.
    if "R" in df.columns:
        df["rank"] = df["R"]
    if (df["ranking"] == "").all():
        df["ranking"] = ""
    return df[OUTPUT_COLUMNS]


def normalize_university(name: str) -> str:
    """Normalize a university name so variants across files match."""
    name = str(name)
    name = re.sub(r"\s*\(.*?\)", "", name)          # drop "(Caltech)", "(Penn State)", ...
    name = name.replace("\u2013", "-").replace("\u2014", "-")  # en/em dash -> hyphen
    name = re.sub(r"\s+", " ", name).strip().lower()
    return name


def university_rankings(frames: list[pd.DataFrame]) -> dict[str, str]:
    """Build a University -> numeric ranking map from the source CSVs.

    Rankings found in the merged frames (combined_faculty.csv) are used first,
    then ranking_2026.csv (the user-provided ranking) overrides where present.
    """
    ranking = {}
    for df in frames:
        if "ranking" not in df.columns:
            continue
        for _, row in df[["university", "ranking"]].drop_duplicates().iterrows():
            uni = normalize_university(row["university"])
            val = str(row["ranking"]).strip()
            if uni and val:
                ranking.setdefault(uni, val)

    if os.path.exists(RANKING_2026_PATH):
        r2026 = pd.read_csv(RANKING_2026_PATH, dtype=str).fillna("")
        col = next((c for c in ("US_News_Rank_2026", "Ranking_2026", "Ranking")
                    if c in r2026.columns), None)
        for _, row in r2026.iterrows():
            uni = normalize_university(row["University"])
            val = str(row[col]).strip()
            if uni and val:
                ranking[uni] = val
    return ranking


def apply_rankings(df: pd.DataFrame, ranking: dict[str, str]) -> pd.DataFrame:
    """Fill the 'ranking' column for every row from the university ranking map."""
    df = df.copy()
    df["ranking"] = df["university"].map(normalize_university).map(ranking).fillna("")
    return df


def deduplicate(df: pd.DataFrame) -> pd.DataFrame:
    """Drop duplicate professors, keeping the row with the most complete info."""
    df = df.copy()
    df["_key"] = df["email"].str.strip().str.lower()
    no_email = df["_key"] == ""
    df.loc[no_email, "_key"] = (
        df.loc[no_email, "university"].str.strip().str.lower()
        + "|"
        + df.loc[no_email, "professor_name"].str.strip().str.lower()
    )
    df["_score"] = df.apply(_completeness, axis=1)
    df = df.sort_values("_score", ascending=False).drop_duplicates(subset="_key", keep="first")
    return df.drop(columns=["_key", "_score"]).reset_index(drop=True)


def main() -> None:
    data_dir = sys.argv[1] if len(sys.argv) > 1 else DATA_DIR
    output_path = sys.argv[2] if len(sys.argv) > 2 else OUTPUT_PATH

    paths = sorted(glob.glob(os.path.join(data_dir, "*.csv")))
    if not paths:
        print(f"No CSV files found in {data_dir}")
        sys.exit(1)

    frames = [load_and_normalize(p) for p in paths]
    merged = pd.concat(frames, ignore_index=True)

    total = len(merged)
    merged = deduplicate(merged)
    deduped = len(merged)

    ranking = university_rankings(frames)
    merged = apply_rankings(merged, ranking)

    ai_df = merged[merged["research_area"].apply(is_ai_related)].copy()
    ai_df = ai_df.sort_values(["university", "professor_name"]).reset_index(drop=True)

    ai_df.to_csv(output_path, index=False, encoding="utf-8")

    print(f"Files merged : {len(paths)}")
    for p in paths:
        print(f"  - {os.path.basename(p)}")
    print(f"Total rows   : {total}")
    print(f"After dedup  : {deduped}")
    print(f"AI related   : {len(ai_df)}")
    print(f"Output       : {output_path}")


if __name__ == "__main__":
    main()
