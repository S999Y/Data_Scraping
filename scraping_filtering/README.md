# AI Professor Filter

A data pipeline that collects computer science faculty data from top-ranked US
universities, filters for AI/ML/NLP/CV research areas, and produces a clean
dataset of AI-relevant professors with their publication metrics and venue
matches.

## Project Overview

This project scrapes faculty listings from CS department websites of R1 and R2
universities, enriches the data with publication metrics from the OpenAlex API,
and filters the results to keep only professors whose research areas fall within
AI, Machine Learning, Natural Language Processing, or Computer Vision.

### Data Pipeline

```
University CS Faculty Pages  -->  Scraped CSVs  -->  merge_ai_professors.py  -->  Final Dataset
       (manual/API)               (combined.csv)     (normalize, dedup,          (merged_ai_professors.csv)
                                                      filter by AI keywords)
```

## Files

### `merge_ai_professors.py` — Core Merge & Filter Script

The main script that produces the final output. It:

1. **Reads** all CSV files from the `data/` directory (`combined.csv`,
   `combined_faculty.csv`, `research_areas.csv`)
2. **Normalizes** column names across different source formats to a common schema
3. **Deduplicates** professors using email (primary) or name+university fallback,
   preferring rows with the most complete information
4. **Applies university rankings** from `ranking_2026.csv` (US News 2026 data)
5. **Filters** to keep only professors with AI/ML/NLP/CV-related research areas
   using regex keyword matching
6. **Outputs** `merged_ai_professors.csv` with 14 normalized columns

**Key functions:**

| Function | Purpose |
|----------|---------|
| `load_and_normalize(path)` | Reads a CSV and maps its columns to the standard output schema |
| `is_ai_related(value)` | Checks if a research area string matches AI/ML/NLP/CV keywords |
| `deduplicate(df)` | Removes duplicate professor entries, keeping the most complete row |
| `normalize_university(name)` | Normalizes university name variants (parentheses, dashes, case) |
| `apply_rankings(df, ranking)` | Fills in numeric university rankings from the ranking map |
| `university_rankings(frames)` | Builds a university-to-ranking dictionary from source CSVs |

**AI keyword filter** (matched case-insensitive):
`ai`, `artificial intelligence`, `machine learning`, `deep learning`,
`reinforcement learning`, `nlp`, `natural language`, `computer vision`,
`vision`, `image processing`, `medical imaging`, `neural`, `neuroai`,
`pattern recognition`, `generative`, `intelligent`, `speech`, `cv`

### `openalex_fetcher.py` — OpenAlex API Enrichment

Optional script for online mode. Queries the
[OpenAlex API](https://openalex.org/) to:

- Look up each professor by name and institution
- Retrieve h-index, citation counts, and publication counts
- Match publications against top AI venues (NeurIPS, ICML, ICLR, CVPR, ACL,
  AAAI, EMNLP, etc.)
- Output `openalex_enriched.csv` with publication metrics

**Usage:**
```bash
python openalex_fetcher.py --input-dir data --delay 0.12
```

The `--delay` parameter controls request throttling (default 0.12s) to respect
the OpenAlex rate limit.

### `config/research_area.json` — Research Area Definitions

JSON configuration defining AI-related research area categories:

- **AI** — Artificial Intelligence (including Explainable AI, Generative AI,
  Human-Centered AI)
- **ML** — Machine Learning (including Deep Learning, Reinforcement Learning)
- **CV** — Computer Vision (including Medical Image Analysis, Graphics)
- **NLP** — Natural Language Processing (including Speech, LLMs)
- **DL/RL/LLM** — Specialized subcategories

### `data/` — Bundled Source Data

| File | Rows | Description |
|------|------|-------------|
| `combined.csv` | 3,845 | Professors from scraped CS department pages with research areas |
| `combined_faculty.csv` | 4,595 | Faculty listings with university rankings |
| `research_areas.csv` | 1,701 | Professors with labeled research areas |
| `ranking_2026.csv` | 41 | US News 2026 CS university rankings |

## How to Run

### Prerequisites

- Python 3.10+
- pip

### Option 1: Offline Demo (Recommended)

Uses the bundled CSV data. No internet connection needed.

**Windows (one-click):**
```
double-click run_offline.bat
```

**Command line:**
```bash
pip install pandas
python merge_ai_professors.py
```

**Output:** `merged_ai_professors.csv` in the `final_code/` directory.

### Option 2: Online Demo

Fetches fresh publication data from the OpenAlex API for 10 well-known AI
professors, then merges. Takes about 30 seconds.

**Requires a free OpenAlex API key** — get one at
[openalex.org/settings/api](https://openalex.org/settings/api). The key is
embedded in `openalex_fetcher.py`.

**Windows (one-click):**
```
double-click run_online.bat
```

**Command line:**
```bash
pip install -r requirements.txt
python openalex_fetcher.py --limit 10
python merge_ai_professors.py
```

**Options:**
- `--limit N` — Number of professors to enrich (default: 10). Use `0` for all.
- `--delay S` — Seconds between API requests (default: 0.15).

### Custom Input

You can provide a custom input directory and output path:

```bash
python merge_ai_professors.py /path/to/csvs /path/to/output.csv
```

## Output Schema

The final `merged_ai_professors.csv` has these columns:

| Column | Description |
|--------|-------------|
| `university` | University name |
| `rank` | Tier: `r1` or `r2` |
| `ranking` | US News numeric ranking |
| `professor_name` | Full name |
| `title` | Academic title |
| `email` | Primary email |
| `mail` | Secondary email |
| `lab_link` | Lab/personal website URL |
| `research_area` | Primary research area |
| `is_pickable` | Whether professor is available for outreach |
| `matched_venues` | Top venues where they have published |
| `n_target_pubs` | Number of papers at target venues |
| `total_publications` | Total publication count |
| `profile_url` | Faculty profile page URL |

## Tech Stack

- **Python 3.10+**
- **pandas** — Data manipulation and CSV I/O
- **requests** — HTTP client for OpenAlex API (online mode only)
- **OpenAlex API** — Open bibliometric data source (online mode only)
