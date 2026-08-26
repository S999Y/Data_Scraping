# Professors Data

> Automated CS faculty profiling system -- scrapes 83+ US universities, enriches profiles via 7 academic APIs, and identifies top AI/ML researchers for graduate school outreach.

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: Academic](https://img.shields.io/badge/License-Academic-green.svg)](#license)

---

## Overview

This project automates the end-to-end pipeline for identifying strong graduate school advisor candidates in Computer Science:

1. **Scrape** CS faculty listings from 83 R1/R2 US universities using 40+ custom HTML parsers
2. **Enrich** professor profiles with citation metrics, h-index, and publication data from 7 free academic APIs
3. **Filter** for AI/ML/NLP/CV research areas and match publications against 11 top-tier venues
4. **Analyze** the collected dataset with exploratory data analysis and predictive models

---

## Project Structure

```
Professors_Data/
|
|-- modular_script_01/          # Core: web scraping + 7-API pipeline
|   |-- driver.py               # Scraping orchestrator (83 universities)
|   |-- adapters.py             # 40+ per-university HTML parsers
|   |-- universities.py         # University metadata (rank, URL, tier)
|   |-- run_demo.py             # Single entry point for all demos
|   |-- test_scraper/           # 7-API data pipeline package
|   |   |-- collectors/         # One collector per API (7 total)
|   |   |-- pipeline.py         # Merge, dedupe, infer topics
|   |   |-- sources.py          # Source registry + priority order
|   |   |-- topics.py           # Research-area tag inference
|   |   |-- rankings.py         # Carnegie R1/R2/R3 lookup
|   |-- modular_scraping/       # Config-driven website scraper engine
|   |-- scholar_scraping/       # Google Scholar profile scraper
|   |-- datasets/               # Scraped faculty CSVs + unified output
|   |-- html_pages/             # Saved HTML fixtures for offline demos
|
|-- filtering_venues/           # Venue matching + pickability scoring
|   |-- scrapers/               # University-specific scrapers
|   |-- test_online.py          # Cached API data verification
|   |-- test_offline.py         # CSV-only pipeline test
|   |-- data/                   # Source CSVs + OpenAlex cache
|   |-- results/                # Test outputs
|
|-- scraping_filtering/         # OpenAlex fetcher + AI professor filter
|   |-- openalex_fetcher.py     # Queries OpenAlex for venue matching
|   |-- merge_ai_professors.py  # Merges, dedupes, filters AI areas
|   |-- config/                 # Research area definitions
|   |-- data/                   # Input CSVs (combined, rankings)
|
|-- eda/                        # Exploratory Data Analysis & ML
|   |-- eda.ipynb               # Full EDA (47 cells)
|   |-- linear_regresion.ipynb  # Predict total citations
|   |-- logistic_regresion.ipynb # Research area classification
|
|-- dataset/                    # Final datasets
|   |-- professors.csv          # 317 professors, 26 columns
|   |-- professors_engineered.csv # 317 professors, 40 columns
|
|-- .gitignore
|-- README.md
|-- USERGUIDE.md                # Comprehensive usage guide
```

---

## Quick Start

### Installation

```bash
git clone <repository-url>
cd Professors_Data
python -m venv venv
.\venv\Scripts\Activate.ps1        # Windows PowerShell
pip install requests beautifulsoup4 pandas openpyxl lxml
```

### Run Demos

```bash
cd modular_script_01

python run_demo.py selftest                           # Validate offline (no network)
python run_demo.py scrape --offline                   # Parse saved HTML pages
python run_demo.py scrape --live --sites mit_eecs     # Live scrape MIT
python run_demo.py single --name "Regina Barzilay"    # 7-API pipeline on one professor
python run_demo.py batch --limit 5                    # Batch process from CSVs
python run_demo.py full --limit 2                     # End-to-end: scrape + enrich
```

### Filter & Merge

```bash
cd scraping_filtering
pip install pandas
python merge_ai_professors.py                         # Offline merge + AI filter
python openalex_fetcher.py --limit 10 --delay 0.15   # Online: fetch from OpenAlex
```

### Venue Matching

```bash
cd filtering_venues
pip install -r requirements.txt
python test_online.py                                 # Cached API data test
python test_offline.py                                # CSV-only test
```

### Run Notebooks

```bash
pip install pandas numpy matplotlib seaborn scikit-learn scipy jupyter nbconvert nbformat
jupyter notebook eda/eda.ipynb
```

---

## The 7-API Data Pipeline

The core enrichment engine queries 7 free academic APIs simultaneously for each professor:

| # | Source | What It Provides |
|---|--------|-----------------|
| 1 | **OpenAlex** | Author profiles, citations, h-index, research topics, papers |
| 2 | **ORCID** | Biography, website, external identifiers |
| 3 | **Crossref** | Paper details, DOI, venue, year, abstract |
| 4 | **DBLP** | Computer Science publication list |
| 5 | **Semantic Scholar** | Metrics, affiliations, research interests, papers |
| 6 | **Google Scholar** | Full profile with all papers and citation metrics |
| 7 | **Faculty Pages** | University listing data from scraped pages |

**Source priority** for conflicting fields: `scholar > openalex > semantic > dblp > crossref > orcid > faculty`

**Research topic tags** inferred: `ML, AI, NLP, CV, Cybersecurity, Data Mining, IoT, Robotics, Bioinformatics, Blockchain, Cloud Computing, HCI, Systems, Theory`

---

## Documentation

| Document | Description |
|----------|-------------|
| [USERGUIDE.md](USERGUIDE.md) | Comprehensive usage guide for every module and command |
| [modular_script_01/README.md](modular_script_01/README.md) | 7-API pipeline architecture and file structure |
| [filtering_venues/README.md](filtering_venues/README.md) | 4-phase venue matching pipeline |
| [scraping_filtering/README.md](scraping_filtering/README.md) | OpenAlex fetcher and AI professor filter |

---

## Dependencies

### Core

| Package | Purpose |
|---------|---------|
| `requests` | HTTP requests for scraping and API calls |
| `beautifulsoup4` | HTML parsing |
| `pandas` | Data manipulation and CSV I/O |
| `openpyxl` | Excel file support |

### Optional

| Package | Purpose |
|---------|---------|
| `lxml` | Faster HTML/XML parsing |
| `playwright` | JavaScript-rendered page support |
| `scikit-learn` | Machine learning models (EDA notebooks) |
| `matplotlib` / `seaborn` | Data visualization |
| `scipy` | Statistical analysis |

---

## License

This project is for academic and research purposes only.
