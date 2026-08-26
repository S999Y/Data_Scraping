# CS Faculty Research Profiling System

A web scraping and data enrichment pipeline that profiles Computer Science faculty members across 84 US universities, enriches their data with publication records from the OpenAlex API, and matches their publications against 11 top-tier AI/ML/CV/NLP conference venues to identify "pickable" professors for graduate school applications.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Pipeline Phases](#pipeline-phases)
4. [Setup & Installation](#setup--installation)
5. [API Key Configuration](#api-key-configuration)
6. [Usage](#usage)
7. [Online vs Offline Modes](#online-vs-offline-modes)
8. [Target Venues & Research Areas](#target-venues--research-areas)
9. [Output Files](#output-files)
10. [Matching Algorithm](#matching-algorithm)
11. [Test Results](#test-results)
12. [Data Directory Structure](#data-directory-structure)

---

## Project Overview

This system automates the process of identifying CS faculty members who are strong candidates for graduate school applications based on:

- **University Rank**: Must be an R1-classified institution
- **Research Area**: Must be in AI/ML/CV/NLP/Cryptography (not "Other")
- **Venue Publications**: Must have published at least one paper in a top-tier venue (2024-2026)

The system processes faculty data from 84 universities, covering approximately 3,845 professors.

---

## Architecture

```
university_data.json
        |
        v
+------------------+
|   Phase 1:       |     scrapers/
|   Scrape Faculty |----> base.py, generic.py, cmu.py, mit.py,
|   (main.py)      |     stanford.py, ucla.py, umkc.py, etc.
+------------------+
        |
        v
+------------------+
|   Phase 2:       |     derive/
|   Classify &     |----> research_area.py, scoring.py
|   Score          |
+------------------+
        |
        v
+------------------+
|   Phase 3:       |     publishers/
|   OpenAlex       |----> openalex.py (API client, venue matching)
|   Enrichment     |
+------------------+
        |
        v
+------------------+
|   Phase 4:       |     output/
|   Export Results |----> writers.py (CSV output)
+------------------+
        |
        v
   results/ (CSV, JSON, TypeScript)
```

---

## Pipeline Phases

### Phase 1: Web Scraping (`--mode scrape`)

- Reads university list from `data/university_data.json` (84 schools)
- Selects appropriate scraper for each university:
  - **Custom scrapers**: MIT, CMU, Stanford, UCLA, UMKC, Tennessee State, Wright State
  - **Generic scraper**: Config-driven CSS selector scraper for all other schools
- Scrapes faculty listing pages using `requests` (with Playwright fallback for JS-rendered pages)
- Optionally follows each professor's profile page for title, email, lab link, and research text
- Classifies research areas using keyword matching
- Outputs to `data/output/combined.csv`

### Phase 2: Research Area Classification

- Uses keyword-based classifier from `derive/research_area.py`
- Matches against 5 target areas with 60+ keywords:
  - Computer Vision, Machine Learning, Artificial Intelligence, NLP, Cryptography & Security
- Supports multi-label classification (professors can match multiple areas)
- Returns "Other" for no keyword match

### Phase 3: OpenAlex Enrichment & Venue Matching (`--mode online`)

- Resolves each professor to an OpenAlex author ID using name + institution scoring
- Fetches author's 2024-2026 publications from OpenAlex API
- Matches each publication's source against 11 target venues
- Computes `is_pickable` based on R1 rank + relevant area + venue publications
- All API calls are cached on disk for zero-cost re-runs

### Phase 4: Export

- Converts CSV results to JSON and TypeScript formats
- Generates per-venue paper counts
- Adds h-index and citation data from OpenAlex

---

## Setup & Installation

### Prerequisites

- Python 3.9+
- pip

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Install Playwright (for JS-rendered pages)

```bash
playwright install chromium
```

### API Keys

The system uses OpenAlex API keys for enrichment. Keys are stored in:
- `data/api/api_key.txt` (primary, 11 keys)
- `config.json` (backup, 4 keys)

API keys are rotated round-robin across requests to stay within rate limits.

---

## API Key Configuration

### OpenAlex API Keys

The system uses [OpenAlex API](https://docs.openalex.org/) for:
- Author resolution (finding a professor's OpenAlex profile)
- Publication fetching (getting their papers)
- Venue matching (identifying top-tier publications)

Keys are loaded from `data/api/api_key.txt` (one key per line) and supplemented by keys in `config.json`.

### Rate Limiting

- Default delay: 0.2 seconds between requests
- Rate limit: 8 requests/second across all workers
- Automatic retry with exponential backoff on 429 errors
- Round-robin key rotation across 15 API keys

---

## Usage

### Full Pipeline (Online Mode)

```bash
# Run complete pipeline: scrape + enrich + venue match
python main.py --mode online

# Limit to first 100 professors
python main.py --mode online --limit 100

# Process only one school
python main.py --mode online --school "Massachusetts Institute of Technology"
```

### Scrape Only

```bash
# Scrape faculty without OpenAlex enrichment
python main.py --mode scrape

# Scrape without following profile pages
python main.py --mode scrape --no-profiles

# Scrape one school with limit
python main.py --mode scrape --school "Carnegie Mellon University" --limit 50
```

### Offline Mode

```bash
# Process from existing CSVs (no API calls)
python main.py --mode offline

# Show top 50 from existing data
python main.py --mode offline --limit 50
```

### Test Runs

```bash
# Online test: re-run venue matching on top 10 from cached data
python test_online.py

# Offline test: process top 10 from CSVs only
python test_offline.py

# Test top 5 instead of 10
python test_online.py --top 5
```

---

## Online vs Offline Modes

### Online Mode

| Feature | Online |
|---------|--------|
| Web scraping | Yes (live requests) |
| OpenAlex API | Yes (with rate limiting) |
| Author resolution | Yes (with caching) |
| Venue matching | Yes (live or cached) |
| API keys required | Yes |
| Network required | Yes |
| Output quality | Full enrichment |

### Offline Mode

| Feature | Offline |
|---------|---------|
| Web scraping | No |
| OpenAlex API | No |
| Author resolution | No (uses existing data) |
| Venue matching | No (uses existing data) |
| API keys required | No |
| Network required | No |
| Output quality | Pre-existing data only |

### Cache System

All OpenAlex API responses are cached on disk:
- `data/cache/author_matches/` - Author resolution results (3,803 files)
- `data/cache/venue_works/` - Publication data (3,476 files)

Re-running with `--mode online` after initial run makes **zero API calls** for cached professors.

---

## Target Venues & Research Areas

### 11 Target Venues

| Venue | Full Name |
|-------|-----------|
| NeurIPS | Neural Information Processing Systems |
| ICML | International Conference on Machine Learning |
| ICLR | International Conference on Learning Representations |
| AAAI | Association for the Advancement of Artificial Intelligence |
| IJCAI | International Joint Conference on Artificial Intelligence |
| CVPR | Computer Vision and Pattern Recognition |
| ICCV | International Conference on Computer Vision |
| ECCV | European Conference on Computer Vision |
| ACL | Association for Computational Linguistics |
| EMNLP | Empirical Methods in Natural Language Processing |
| NAACL | North American Chapter of the Association for Computational Linguistics |

### 5 Research Areas

| Area | Example Keywords |
|------|-----------------|
| Computer Vision | object detection, image segmentation, 3D vision, visual recognition |
| Machine Learning | deep learning, neural networks, reinforcement learning, optimization |
| Artificial Intelligence | knowledge graphs, automated reasoning, multi-agent systems |
| NLP | language models, machine translation, text generation, dialogue |
| Cryptography & Security | encryption, blockchain, zero-knowledge proofs, privacy |

---

## Output Files

### Main Outputs (`results/`)

| File | Description |
|------|-------------|
| `combined.csv` | Full professor list with venue matching results |
| `author_matches.csv` | OpenAlex author resolution details per professor |
| `top_venue_papers.csv` | Individual papers matched to target venues |
| `final_professor_results.csv` | Summary with paper counts and pickability |

### Test Outputs (`results/`)

| File | Description |
|------|-------------|
| `test_online_results.csv` | Online test verification results |
| `test_offline_results.csv` | Offline test verification results |

### Legacy Outputs (`data/output/`)

| File | Description |
|------|-------------|
| `combined.csv` | Combined scraped data (3,845 rows) |
| `research_areas.csv` | Same as combined.csv (for venue_match.py input) |
| `final_professor_results.csv` | Full venue matching results |
| `author_matches.csv` | Author resolution log |

---

## Matching Algorithm

### Author Resolution

For each professor, the system:

1. **Searches OpenAlex** by name
2. **Scores candidates** using:
   - Name similarity (exact match = 1.0, subset = 0.7, partial = 0.6)
   - Institution match (ROR ID or name match = 1.0)
   - Combined score: `name_score * 3 + inst_score * 5`
3. **Decides status**:
   - `MATCHED`: Clear best candidate with institution match
   - `REVIEW`: Ambiguous, needs human review
   - `NOT_FOUND`: No suitable candidate found

### Venue Matching

For each author's publications:

1. **Extracts source name** from OpenAlex work
2. **Normalizes** (lowercase, remove special characters)
3. **Matches against** 11 venue alias lists
4. **Counts matches** per venue and total

### Pickability Rules

A professor is "pickable" if ALL conditions are met:
- University rank is "r1"
- Research area is not "Other" (or is a recognized area)
- Has >= 1 paper in a target venue (2024-2026)

---

## Test Results

### Top 10 Best Matches (by venue paper count)

| Rank | Professor | University | Papers | Venues |
|------|-----------|------------|--------|--------|
| 1 | Xiaowei Jia | University of Pittsburgh | 10 | AAAI |
| 2 | Vincent Conitzer | Carnegie Mellon University | 9 | AAAI |
| 3 | Alan Fern | Oregon State University | 8 | AAAI |
| 4 | Kuldeep S. Meel | Georgia Tech | 8 | AAAI |
| 5 | Tianlong Chen | UNC Chapel Hill | 8 | AAAI |
| 6 | Tuomas Sandholm | Carnegie Mellon University | 8 | AAAI |
| 7 | Meiyi Ma | Vanderbilt University | 6 | AAAI |
| 8 | Percy Liang | Stanford University | 6 | AAAI;ACL |
| 9 | Peter Stone | UT Austin | 6 | AAAI |
| 10 | Yexiang Xue | Purdue University | 6 | AAAI |

### Running the Tests

```bash
# Online test (uses cached API data)
python test_online.py

# Offline test (CSV only)
python test_offline.py
```

---

## Data Directory Structure

```
final_code/
|-- main.py                    # Unified pipeline entry point
|-- test_online.py             # Online test (cached API data)
|-- test_offline.py            # Offline test (CSV only)
|-- config.json                # Configuration
|-- requirements.txt           # Dependencies
|-- README.md                  # This file
|
|-- scrapers/                  # Web scraping package
|   |-- __init__.py            # Registry + make_scraper()
|   |-- base.py                # BaseScraper (requests + Playwright)
|   |-- generic.py             # GenericScraper (config-driven)
|   |-- cmu.py                 # CMU custom scraper
|   |-- mit.py                 # MIT custom scraper
|   |-- stanford.py            # Stanford custom scraper
|   |-- ucla.py                # UCLA custom scraper
|   |-- umkc.py                # UMKC custom scraper
|   |-- tnstate.py             # Tennessee State scraper
|   |-- wright.py              # Wright State scraper
|
|-- publishers/                # API enrichment package
|   |-- __init__.py
|   |-- openalex.py            # OpenAlex API client + venue matching
|
|-- derive/                    # Data derivation package
|   |-- __init__.py
|   |-- research_area.py       # Keyword-based classifier
|   |-- scoring.py             # Row builder + pickability
|
|-- output/                    # Output writers package
|   |-- __init__.py
|   |-- writers.py             # CSV output (standard + streaming)
|
|-- data/                      # Data files
|   |-- university_data.json   # 84 universities with URLs
|   |-- school_config.json     # Per-school CSS selector configs
|   |-- ror_map.json           # University -> ROR ID mapping
|   |-- api/
|   |   |-- api_key.txt        # 11 OpenAlex API keys
|   |-- cache/
|   |   |-- author_matches/    # 3,803 cached author resolutions
|   |   |-- venue_works/       # 3,476 cached publication fetches
|   |-- output/
|       |-- combined.csv       # Combined scraped data
|       |-- research_areas.csv # Research area classifications
|       |-- final_professor_results.csv
|       |-- author_matches.csv
|       |-- top_venue_papers.csv
|
|-- results/                   # Test and pipeline outputs
    |-- test_online_results.csv
    |-- test_offline_results.csv
```

---

## License

This project is for academic/research purposes.

---

## Contact

CS Faculty Research Profiling System - Graduate School Research Tool
