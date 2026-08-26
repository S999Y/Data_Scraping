# Automatic Scraping Project

## University Faculty Web Scraping + 7-API Data Pipeline

A complete system for automatically scraping Computer Science faculty data from
83 US university websites and enriching professor profiles using 7 free academic
APIs.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [System Architecture](#system-architecture)
3. [Component 1: University Web Scraping](#component-1-university-web-scraping)
4. [Component 2: 7-API Data Pipeline](#component-2-7-api-data-pipeline)
5. [How to Run](#how-to-run)
6. [Demo Commands](#demo-commands)
7. [File Structure](#file-structure)
8. [Technical Details](#technical-details)

---

## Project Overview

This project automates two key tasks:

### Task 1: University Faculty Scraping
- Scrapes CS faculty listing pages from **83 US universities** (R1 and R2 classified)
- Uses **40+ custom per-university parsers** for different website layouts
- Extracts: professor name, email, title, lab link, research areas
- Handles pagination, JavaScript-rendered pages, and Cloudflare email protection

### Task 2: 7-API Data Pipeline
- Enriches scraped professor data using **7 free academic APIs**:
  1. **OpenAlex** - Author profiles, citations, h-index, research topics
  2. **ORCID** - Biographies, websites, external identifiers
  3. **Crossref** - Paper details, DOIs, venues, abstracts
  4. **DBLP** - CS publication lists
  5. **Semantic Scholar** - Metrics, affiliations, research interests
  6. **Google Scholar** - Full profiles and publication lists
  7. **Faculty Pages** - University listing data
- Merges data from all sources with priority-based conflict resolution
- Deduplicates publications by normalized title / DOI
- Infers research topics (ML, NLP, CV, etc.) from text
- Looks up university Carnegie classification (R1/R2/R3)

---

## System Architecture

```
University Websites (83 schools)
         |
         v
+------------------+
|  driver.py       |  <-- Main scraping orchestrator
|  adapters.py     |  <-- 40+ per-university HTML parsers
|  universities.py |  <-- University metadata (name, URL, ranking)
+------------------+
         |
         v
  datasets/faculty/*.csv  (one CSV per university)
         |
         v
+-------------------+
|  test_scraper/    |  <-- 7-API data pipeline
|  collectors/      |  <-- One collector per API source
|  pipeline.py      |  <-- Merge, dedupe, infer topics
|  sources.py       |  <-- Source registry + priority
+-------------------+
         |
         v
  datasets/unified/professor_master.csv  (one row per professor)
  datasets/unified/publications.csv      (one row per paper)
```

---

## Component 1: University Web Scraping

### How It Works

1. **University Metadata** (`universities.py`)
   - Contains 83 university entries with name, Carnegie rank, US News ranking, and faculty page URL
   - Example: `{'name': 'MIT', 'r': 'r1', 'ranking': '2', 'faculty_url': 'https://www.eecs.mit.edu/...'}`

2. **Per-University Parsers** (`adapters.py`)
   - 40+ custom parser functions, one per university
   - Each parser handles the specific HTML structure of that university's faculty page
   - Examples: `parse_mit_eecs()`, `parse_berkeley()`, `parse_stanford()`, `parse_cmu_csd()`
   - Falls back to `parse_generic()` for universities without custom parsers

3. **Orchestrator** (`driver.py`)
   - Maps each university to its parser and pagination strategy
   - Supports: single page, query pagination, Harvard-style, NCSU-style, alphabetical, JS-rendered
   - Handles Wayback Machine fallback for some sites
   - Outputs per-university CSVs + combined CSV

### Supported Pagination Types

| Type | Description | Example |
|------|-------------|---------|
| `None` | Single page | MIT, Berkeley, Stanford |
| `query` | `?page=N` | CMU, OSU, Georgia Tech |
| `harvard` | `?page=%2CN` | Harvard SEAS |
| `ncsu` | `/page/N/` | NC State |
| `alpha` | `/faculty/{letter}` | Georgia Tech |
| `js` | Playwright rendering | UCLA, Rice, Yale |
| `wayback` | Internet Archive | UMich |

### University Coverage

- **83 universities** total (R1 and R2 Carnegie classified)
- **82 individual faculty CSVs** already scraped
- **4,594 total faculty** members in the combined dataset

---

## Component 2: 7-API Data Pipeline

### Data Sources

| # | Source | API Endpoint | Provides | API Key? |
|---|--------|-------------|----------|----------|
| 1 | OpenAlex | api.openalex.org | Profile, citations, h-index, topics, papers | Optional (10x budget) |
| 2 | ORCID | pub.orcid.org | Bio, website, identifiers | No |
| 3 | Crossref | api.crossref.org | Paper details, DOI, venue, year, abstract | No |
| 4 | DBLP | dblp.org | CS publication list | No |
| 5 | Semantic Scholar | api.semanticscholar.org | Metrics, affiliations, interests, papers | No |
| 6 | Google Scholar | scholar.google.com | Full profile + all papers | No (needs URL) |
| 7 | Faculty Pages | (local HTML) | University listing data | No |

### Pipeline Flow

```
Input: Professor name + optional URLs
         |
         v
   +-- OpenAlex --+
   +-- ORCID ----+|
   +-- Crossref -+|
   +-- DBLP -----+|
   +-- Semantic -+|
   +-- Scholar --+|
   +-- Faculty --+|
         |
         v
   Merge Results
   - Profile fields: priority order (scholar > openalex > semantic > ...)
   - Publications: deduplicate by normalized title / DOI
         |
         v
   Infer Topics (ML, NLP, CV, Cybersecurity, etc.)
         |
         v
   Lookup University Rank (Carnegie R1/R2/R3)
         |
         v
Output: professor_master.csv + publications.csv
```

### Source Priority for Conflicting Fields

When multiple sources provide the same field, the highest-priority source wins:
`scholar > openalex > semantic > dblp > crossref > orcid > faculty`

### Research Topic Tags

The system infers these research areas from text:
`ML, AI, NLP, CV, Cybersecurity, Data Mining, IoT, Robotics, Bioinformatics, Blockchain, Cloud Computing, HCI, Systems, Theory`

---

## How to Run

### Prerequisites

```bash
# Python 3.7+ required
python --version

# Install dependencies
pip install -r requirements.txt
```

### Dependencies

- `requests` - HTTP requests for web scraping and API calls
- `beautifulsoup4` - HTML parsing
- `pandas` - Data manipulation and CSV handling
- `openpyxl` - Excel file support

### Quick Start

```bash
# Navigate to the final_code directory
cd final_code

# Run offline selftest (validates everything without internet)
python run_demo.py selftest
```

---

## Demo Commands

### 1. Offline Self-Test (No Internet)

```bash
python run_demo.py selftest
```

Validates the entire pipeline using saved HTML fixtures. Tests:
- Google Scholar profile parsing (offline)
- Topic inference
- University rank lookup
- Merge and save logic

### 2. Parse Saved HTML Pages (No Internet)

```bash
python run_demo.py scrape --offline
```

Parses pre-saved HTML pages from `html_pages/` using the custom university parsers.
Shows how each adapter extracts faculty data from different website layouts.

### 3. Live Scrape University Websites

```bash
# Scrape specific universities
python run_demo.py scrape --live --sites mit_eecs berkeley

# Scrape all available sites
python run_demo.py scrape --live
```

Makes live HTTP requests to university faculty pages and extracts professor data.
Uses our 40+ custom parsers to handle different HTML structures.

### 4. 7-API Pipeline on One Professor

```bash
python run_demo.py single --name "Regina Barzilay"
python run_demo.py single --name "Geoffrey Hinton"
```

Collects data from all 7 APIs for a single professor. Shows:
- Profile metrics (citations, h-index, i10-index)
- University affiliation and rank
- Research topics
- Publication list

### 5. Batch Process Multiple Professors

```bash
python run_demo.py batch --limit 5
```

Processes multiple professors from the scraped faculty CSVs.
Each professor is enriched with API data.

### 6. Full Pipeline Demo (End-to-End)

```bash
python run_demo.py full --limit 2
```

Demonstrates the complete workflow:
1. Scrape faculty from university websites
2. Enrich each professor with API data
3. Generate unified output CSVs

### Output Files

After running the pipeline, these files are created:

| File | Description |
|------|-------------|
| `datasets/faculty/<university>_faculty.csv` | Per-university scraped faculty |
| `datasets/faculty/demo_combined_faculty.csv` | Combined scraped faculty |
| `datasets/unified/professor_master.csv` | One row per professor (all API data merged) |
| `datasets/unified/publications.csv` | One row per paper (deduplicated) |
| `datasets/cache/*.json` | Cached API responses (7-day TTL) |

---

## File Structure

```
final_code/
|
|-- run_demo.py                 # Single entry point for all demos
|-- requirements.txt            # Python dependencies
|-- README.md                   # This file
|
|-- driver.py                   # University scraping orchestrator (83 schools)
|-- adapters.py                 # 40+ per-university HTML parsers (1378 lines)
|-- universities.py             # University metadata (name, URL, ranking)
|
|-- modular_scraping/           # Config-driven website scraper package
|   |-- __init__.py
|   |-- scraper.py              # ConfigurableScraper engine
|   |-- configs.py              # Pre-made configs (JHU, MIT, CMU, Scholar)
|   |-- config_builder.py       # Helper to build configs
|   |-- faculty.py              # CSE check + faculty page scraper
|   |-- analyze_html.py         # HTML structure analysis tool
|   |-- utils.py                # Utilities (validate, save, export)
|
|-- scholar_scraping/           # Google Scholar profile scraper
|   |-- __init__.py
|   |-- scraper.py              # ScholarScraper with full pagination
|   |-- config.py               # Complete Scholar extraction config
|
|-- test_scraper/               # 7-API data pipeline
|   |-- __init__.py
|   |-- _paths.py               # Central path constants
|   |-- test.py                 # User-facing entry point
|   |-- pipeline.py             # Merge, dedupe, infer topics, save
|   |-- sources.py              # Source registry + priority order
|   |-- topics.py               # Research-area tag inference
|   |-- rankings.py             # Carnegie R1/R2/R3 lookup
|   |-- storage/                # JSON cache + CSV helpers
|   |   |-- __init__.py
|   |   |-- cache.py            # JsonCache with TTL
|   |   |-- csv.py              # Read/write/append/dedupe CSVs
|   |-- collectors/             # One collector per data source
|       |-- __init__.py
|       |-- base.py             # Shared HTTP + cache + retries
|       |-- openalex.py         # OpenAlex API collector
|       |-- orcid.py            # ORCID API collector
|       |-- crossref.py         # Crossref API collector
|       |-- dblp.py             # DBLP API collector
|       |-- semantic.py         # Semantic Scholar API collector
|       |-- scholar.py          # Google Scholar collector
|       |-- faculty.py          # Faculty page collector
|
|-- datasets/                   # Data files
|   |-- faculty/                # Scraped faculty CSVs
|   |-- cache/                  # Cached API responses
|   |-- rankings/               # Carnegie rankings
|   |-- unified/                # Output datasets
|
|-- html_pages/                 # Saved HTML for offline demos
    |-- faculty/                # University faculty pages
    |-- scholar.html            # Google Scholar profile
```

---

## Technical Details

### Web Scraping Approach

- Uses `requests` + `BeautifulSoup` for HTML parsing
- Custom per-university adapters for 40+ different website layouts
- Generic fallback parser for unknown layouts
- Playwright support for JavaScript-rendered pages
- Wayback Machine fallback for archived pages
- Cloudflare email protection decoding
- Rate limiting (0.8s delay between requests)

### API Collection Approach

- All 7 APIs are **free** (no API keys required except optional OpenAlex key)
- HTTP session with polite User-Agent header
- JSON cache with 7-day TTL to avoid redundant requests
- Exponential backoff retry (3 attempts)
- Rate limiting between requests (0.3s default)

### Data Merging Strategy

- Profile fields taken by source priority (scholar > openalex > semantic > ...)
- Publications deduplicated by normalized title or DOI
- Research topics inferred from interests, paper titles, and bio text
- University rank looked up from Carnegie classification data

### Windows Compatibility

- UTF-8-sig encoding for Excel-compatible CSV output
- Forward-slash paths used throughout
- Compatible with Windows PowerShell

---

## Troubleshooting

### "No module named requests"
```bash
pip install -r requirements.txt
```

### "Connection refused" during live scraping
- Check internet connection
- Some university sites may block rapid requests
- Use `--offline` mode with saved HTML pages instead

### "No data found" for a professor
- Try a different professor name (more common names work better)
- The APIs may need time to index very recent publications
- Check the API cache in `datasets/cache/` for cached results

### Cache issues
- Delete files in `datasets/cache/*.json` to force fresh API calls
- Cache has a 7-day TTL by default

---

## License

This project was developed for academic/educational purposes.
