# User Guide

Comprehensive guide for using every component of the Professors Data system.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [modular_script_01/ -- Core Scraping + 7-API Pipeline](#modular_script_01----core-scraping--7-api-pipeline)
3. [filtering_venues/ -- Venue Matching & Pickability](#filtering_venues----venue-matching--pickability)
4. [scraping_filtering/ -- OpenAlex Fetcher + AI Filter](#scraping_filtering----openalex-fetcher--ai-filter)
5. [eda/ -- Exploratory Data Analysis & Machine Learning](#eda----exploratory-data-analysis--machine-learning)
6. [dataset/ -- Raw & Engineered Datasets](#dataset----raw--engineered-datasets)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

| Requirement | Minimum Version | Notes |
|-------------|----------------|-------|
| Python | 3.10+ | Required for type hint syntax (`str \| None`) |
| pip | Latest | Package installer |
| Internet | Optional | Only needed for live scraping and API calls |

### Install Dependencies

```bash
# Core dependencies (all modules)
pip install requests beautifulsoup4 pandas openpyxl

# For venue matching module
pip install lxml playwright

# For EDA and machine learning notebooks
pip install numpy matplotlib seaborn scikit-learn scipy jupyter nbconvert nbformat
```

### Install Playwright (Optional)

Only needed for JavaScript-rendered university pages (UCLA, Rice, Yale, VSU, Wright State):

```bash
playwright install chromium
```

---

## modular_script_01/ -- Core Scraping + 7-API Pipeline

This is the main component. It contains two major subsystems: a web scraping engine that collects CS faculty data from 83 US universities, and a 7-API data pipeline that enriches each professor's profile with publication metrics, citations, and research topics.

### 1. University Web Scraping

#### How It Works

The scraping system has three layers:

**Layer 1: University Metadata** (`universities.py`)
- Contains 83 university entries with name, Carnegie classification (R1/R2), US News ranking, and faculty page URL
- Example entry:
  ```python
  {'name': 'Massachusetts Institute of Technology', 'r': 'r1', 'ranking': '2',
   'faculty_url': 'https://www.eecs.mit.edu/role/faculty-cs/', 'reuse': None}
  ```

**Layer 2: Per-University Parsers** (`adapters.py`)
- 40+ custom parser functions, one per university
- Each parser handles the specific HTML structure of that university's faculty page
- Examples: `parse_mit_eecs()`, `parse_berkeley()`, `parse_stanford()`, `parse_cmu_csd()`
- Falls back to `parse_generic()` for universities without custom parsers

**Layer 3: Scraping Orchestrator** (`driver.py`)
- Maps each university to its parser and pagination strategy
- Handles fetching (requests, Playwright, Wayback Machine)
- Deduplicates faculty by name
- Outputs per-university CSVs + combined CSV

#### Supported Pagination Types

| Type | URL Pattern | Example Universities |
|------|-------------|---------------------|
| `None` | Single page | MIT, Berkeley, Stanford, UCSD |
| `query` | `?page=N` | CMU, OSU, Georgia Tech, Clark Atlanta |
| `harvard` | `?page=%2CN` | Harvard SEAS |
| `ncsu` | `/page/N/` | NC State |
| `alpha` | `/faculty/{letter}` | Georgia Tech |
| `js` | Playwright rendering | UCLA, Rice, Yale, VSU, Wright State |
| `wayback` | Internet Archive | UMich |

#### Running the Scraper

**Offline mode** (parse saved HTML pages, no network needed):

```bash
cd modular_script_01
python run_demo.py scrape --offline
```

**Live mode** (scrape real university websites):

```bash
# Scrape all available sites
python run_demo.py scrape --live

# Scrape specific universities by slug
python run_demo.py scrape --live --sites mit_eecs berkeley stanford

# Scrape directly with driver.py
python driver.py mit_eecs berkeley       # specific sites
python driver.py                          # all sites
python driver.py --offline                # parse saved HTML
python driver.py --reuse-only             # copy existing CSVs
```

**Output files:**
- `datasets/faculty/<slug>_faculty.csv` -- Per-university faculty data
- `datasets/faculty/combined_faculty.csv` -- Combined output from all universities

#### Scraping Output Schema

Each row contains:

| Column | Description |
|--------|-------------|
| `University` | University name |
| `R` | Carnegie classification (`r1` or `r2`) |
| `Ranking` | US News numeric ranking |
| `Professor name` | Full name |
| `Email` | Primary email address |
| `Mail` | Secondary email (rare) |
| `Lab link` | Personal/lab website URL |
| `Research area` | Research specializations |

#### Custom Parser Example

To add a new university parser, add a function to `adapters.py`:

```python
def parse_my_university(soup, base):
    rows = []
    for card in soup.find_all('div', class_='faculty-card'):
        name = _txt(card.find('h3'))
        email, mail = _emails_from(card)
        link = urljoin(base, card.find('a', href=True)['href'])
        rows.append({'name': name, 'title': '', 'email': email,
                     'mail': mail, 'lab_link': link, 'research': ''})
    return rows
```

Then register it in `driver.py`:

```python
STATIC_PARSERS = {
    'my_university': (parse_my_university, None),  # None = no pagination
    ...
}
SLUG_TO_UNIV = {
    'my_university': 'My University Name',
    ...
}
```

### 2. 7-API Data Pipeline

Located in `test_scraper/`. This subsystem collects professor data from 7 free academic APIs, merges the results, and produces unified output CSVs.

#### API Sources

| # | Collector | File | API Endpoint | Key Required |
|---|-----------|------|-------------|-------------|
| 1 | OpenAlex | `collectors/openalex.py` | api.openalex.org | Optional (10x budget) |
| 2 | ORCID | `collectors/orcid.py` | pub.orcid.org | No |
| 3 | Crossref | `collectors/crossref.py` | api.crossref.org | No |
| 4 | DBLP | `collectors/dblp.py` | dblp.org | No |
| 5 | Semantic Scholar | `collectors/semantic.py` | api.semanticscholar.org | No |
| 6 | Google Scholar | `collectors/scholar.py` | scholar.google.com | No (needs profile URL) |
| 7 | Faculty Pages | `collectors/faculty.py` | Local HTML | No |

#### Running the Pipeline

**Single professor:**

```bash
cd modular_script_01

# Via demo runner
python run_demo.py single --name "Regina Barzilay"
python run_demo.py single --name "Geoffrey Hinton"

# Via Python API
python -c "
from test_scraper.test import scrape_professor
scrape_professor('Regina Barzilay')
"
```

**Batch processing:**

```bash
# Process professors from scraped faculty CSVs
python run_demo.py batch --limit 5

# Via Python API
python -c "
from test_scraper.test import run_batch
run_batch(limit=10)
"
```

**Offline selftest** (validates pipeline without network):

```bash
python run_demo.py selftest
```

**Full end-to-end demo** (scrape + enrich + output):

```bash
python run_demo.py full --limit 2
```

#### Source Priority

When multiple APIs provide the same field, the highest-priority source wins:

```
scholar > openalex > semantic > dblp > crossref > orcid > faculty
```

This means Google Scholar data takes precedence over OpenAlex for the same field, and so on.

#### Output Files

| File | Description |
|------|-------------|
| `datasets/unified/professor_master.csv` | One row per professor (all API data merged) |
| `datasets/unified/publications.csv` | One row per paper (deduplicated) |
| `datasets/cache/*.json` | Cached API responses (7-day TTL) |

#### Professor Master Schema

| Field | Description |
|-------|-------------|
| `name` | Professor name |
| `university` | Affiliated university |
| `department` | Department name |
| `country` | Country |
| `position` | Academic title |
| `email` | Email address |
| `website` | Personal website |
| `total_citations` | Total citation count |
| `h_index` | h-index |
| `i10_index` | i10-index |
| `total_publications` | Total paper count |
| `research_topics` | Inferred research areas (semicolon-separated) |
| `rank` | Carnegie R1/R2/R3 classification |
| `sources` | Which APIs contributed data |

#### Publication Schema

| Field | Description |
|-------|-------------|
| `professor` | Professor name |
| `title` | Paper title |
| `abstract` | Paper abstract |
| `venue` | Publication venue |
| `year` | Publication year |
| `citations` | Citation count |
| `doi` | Digital Object Identifier |
| `source` | Which API provided this paper |

#### Research Topic Inference

The pipeline infers research topics from interests, paper titles, and bio text using keyword matching against these categories:

| Tag | Example Keywords |
|-----|-----------------|
| ML | machine learning, deep learning, neural network, transformer, LLM |
| AI | artificial intelligence, knowledge representation, automated planning |
| NLP | natural language, text mining, machine translation, dialogue |
| CV | computer vision, image processing, object detection, 3D vision |
| Cybersecurity | cryptography, network security, privacy, encryption |
| Data Mining | data mining, clustering, anomaly detection |
| Robotics | robotics, autonomous driving, manipulation, SLAM |
| Bioinformatics | genomics, proteomics, drug discovery, biomedical |
| Theory | algorithm, computational complexity, optimization |

### 3. Modular Scraping Engine

Located in `modular_scraping/`. A config-driven scraper engine for extracting data from arbitrary website structures.

#### Using the ConfigurableScraper

```python
from modular_scraping.scraper import ConfigurableScraper

config = {
    'name': 'My University - CS Faculty',
    'container': {'tag': 'div', 'class': 'faculty-card'},
    'extractors': [
        {'field': 'name', 'selector': {'tag': 'h3'}, 'type': 'text', 'required': True},
        {'field': 'email', 'selector': {'tag': 'a', 'attribute': 'href'}, 'type': 'attribute'},
        {'field': 'title', 'selector': {'tag': 'p', 'class': 'title'}, 'type': 'text'},
    ],
    'delay': 1.5
}

scraper = ConfigurableScraper(config, output_file='faculty.csv')
results = scraper.scrape('https://university.edu/faculty')
scraper.save(fmt='csv')
```

#### Pre-built Configurations

| Config Key | University |
|-----------|-----------|
| `john_hopkins_config` | Johns Hopkins University CS |
| `mit_profed_config` | MIT Professional Education |
| `cmu_university_professors_config` | CMU University Professors |
| `SCHOLAR_CONFIG` | Google Scholar Profile |

### 4. Google Scholar Scraper

Located in `scholar_scraping/`. A dedicated scraper for Google Scholar citation profile pages.

#### Features

- Full publication list loading via pagination (batches of 100)
- Extracts: name, affiliation, h-index, i10-index, total citations, all publications
- Supports both live URL and saved HTML file input

#### Usage

```python
from scholar_scraping.scraper import ScholarScraper

scraper = ScholarScraper()

# Live scrape
records = scraper.scrape_scholar('https://scholar.google.com/citations?user=XXXXX')

# Offline from saved HTML
records = scraper.scrape_from_file('html_pages/scholar.html')

# Collect without saving
data = scraper.collect_data(url='https://scholar.google.com/citations?user=XXXXX')
profile = data['profile']
publications = data['publications']
```

---

## filtering_venues/ -- Venue Matching & Pickability

A 4-phase pipeline that profiles CS faculty across 84 universities, enriches their data with OpenAlex publication records, and matches their publications against 11 top-tier AI/ML/CV/NLP conference venues to identify "pickable" professors.

### Pipeline Architecture

```
Phase 1: Web Scrape  -->  Phase 2: Classify  -->  Phase 3: OpenAlex Enrich  -->  Phase 4: Export
 (main.py)               (derive/)               (publishers/)                  (output/)
```

### Phase 1: Web Scraping

```bash
# Scrape all 84 universities
python main.py --mode scrape

# Scrape without following profile pages
python main.py --mode scrape --no-profiles

# Scrape one school with limit
python main.py --mode scrape --school "Carnegie Mellon University" --limit 50
```

**Custom scrapers** for: MIT, CMU, Stanford, UCLA, UMKC, Tennessee State, Wright State
**Generic scraper**: Config-driven CSS selector scraper for all other schools

### Phase 2: Research Area Classification

Automatic classification using keyword matching across 5 target areas:

| Area | Example Keywords |
|------|-----------------|
| Computer Vision | object detection, image segmentation, 3D vision |
| Machine Learning | deep learning, neural networks, reinforcement learning |
| Artificial Intelligence | knowledge graphs, automated reasoning, multi-agent |
| NLP | language models, machine translation, text generation |
| Cryptography & Security | encryption, blockchain, zero-knowledge proofs |

### Phase 3: OpenAlex Enrichment & Venue Matching

```bash
# Full online pipeline (scrape + enrich + match)
python main.py --mode online

# Limit to first 100 professors
python main.py --mode online --limit 100

# Process only one school
python main.py --mode online --school "Massachusetts Institute of Technology"
```

**11 Target Venues:**

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

### Phase 4: Export

Results are exported to `results/` as CSV, JSON, and TypeScript formats.

### Running Tests

**Online test** (uses cached API data, no live calls):

```bash
python test_online.py
python test_online.py --top 5
```

**Offline test** (CSV-only, no API calls):

```bash
python test_offline.py
python test_offline.py --top 5
```

### Pickability Rules

A professor is "pickable" if ALL conditions are met:

1. University rank is `r1`
2. Research area is not `Other`
3. Has at least 1 paper in a target venue (2024-2026)

### Cache System

All OpenAlex API responses are cached on disk:

- `data/cache/author_matches/` -- Author resolution results
- `data/cache/venue_works/` -- Publication data

Re-running with `--mode online` after initial run makes **zero API calls** for cached professors.

### Matching Algorithm

**Author Resolution:**

1. Search OpenAlex by name
2. Score candidates using name similarity + institution match
3. Combined score: `name_score * 3 + inst_score * 5`
4. Status: `MATCHED`, `REVIEW`, or `NOT_FOUND`

**Venue Matching:**

1. Extract source name from each OpenAlex work
2. Normalize (lowercase, remove special characters)
3. Match against 11 venue alias lists
4. Count matches per venue and total

---

## scraping_filtering/ -- OpenAlex Fetcher + AI Filter

A simpler pipeline for fetching professor publication data from OpenAlex and filtering for AI/ML/NLP/CV research areas.

### Files

| File | Purpose |
|------|---------|
| `openalex_fetcher.py` | Queries OpenAlex API for publication data & venue matching |
| `merge_ai_professors.py` | Merges CSVs, normalizes, deduplicates, filters for AI areas |
| `config/research_area.json` | Research area category definitions |
| `data/combined.csv` | 3,845 professors from scraped pages |
| `data/combined_faculty.csv` | 4,595 faculty with rankings |
| `data/ranking_2026.csv` | US News 2026 CS rankings |

### Offline Mode (No Internet)

```bash
cd scraping_filtering

# Windows: double-click run_offline.bat
# Or command line:
python merge_ai_professors.py
```

This reads all CSVs from `data/`, normalizes columns, deduplicates professors, applies university rankings, and filters for AI-related research areas.

**Output:** `merged_ai_professors.csv`

### Online Mode (With Internet)

```bash
cd scraping_filtering

# Windows: double-click run_online.bat
# Or command line:
python openalex_fetcher.py --limit 10 --delay 0.15
python merge_ai_professors.py
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--limit N` | 10 | Number of professors to enrich (0 = all) |
| `--delay S` | 0.15 | Seconds between API requests |
| `--input-dir` | `data/` | Directory containing input CSVs |

### Custom Input

```bash
python merge_ai_professors.py /path/to/csvs /path/to/output.csv
```

### AI Keyword Filter

The `is_ai_related()` function matches these keywords (case-insensitive):

`ai`, `artificial intelligence`, `machine learning`, `deep learning`, `reinforcement learning`, `nlp`, `natural language`, `computer vision`, `vision`, `image processing`, `medical imaging`, `neural`, `neuroai`, `pattern recognition`, `generative`, `intelligent`, `speech`, `cv`

### Output Schema

| Column | Description |
|--------|-------------|
| `university` | University name |
| `rank` | Tier: `r1` or `r2` |
| `ranking` | US News numeric ranking |
| `professor_name` | Full name |
| `title` | Academic title |
| `email` | Primary email |
| `research_area` | Primary research area |
| `matched_venues` | Top venues where they have published |
| `n_target_pubs` | Number of papers at target venues |
| `total_publications` | Total publication count |
| `profile_url` | Faculty profile page URL |

---

## eda/ -- Exploratory Data Analysis & Machine Learning

Three Jupyter notebooks for analyzing the professor dataset.

### Notebook 1: Exploratory Data Analysis (`eda.ipynb`)

**47 cells** performing comprehensive EDA:

1. **Data Loading & Overview** -- Shape, types, basic statistics
2. **Missing Value Analysis** -- Bar chart, gaps per column
3. **Univariate Analysis** -- Distributions, box plots, category counts
4. **Bivariate Analysis** -- Rank vs papers, h-index vs citations, heatmaps
5. **Multivariate Analysis** -- Pair plots, violin plots, 3D scatter
6. **Correlation Analysis** -- Heatmaps, top correlated pairs, clustered heatmap
7. **Feature Engineering** -- 14 new features (see dataset section)

**Run:**
```bash
jupyter notebook eda/eda.ipynb
# Or non-interactively:
python -m nbconvert --to notebook --execute --ExecutePreprocessor.timeout=600 eda/eda.ipynb --output eda.ipynb
```

### Notebook 2: Linear Regression (`linear_regresion.ipynb`)

**39 cells** predicting total citations:

1. Data loading and cleaning
2. Feature engineering (14 features)
3. Log-transform target: `y = log(total_citations + 1)`
4. Models: OLS, Ridge, Lasso with alpha tuning
5. Evaluation: R-squared, RMSE, MAE, 5-fold CV
6. Residual diagnostics, Q-Q plots, Shapiro-Wilk test
7. Feature importance analysis

### Notebook 3: Logistic Regression (`logistic_regresion.ipynb`)

**37 cells** with two classification tasks:

**Task 1: Binary Classification (High Impact Professor)**
- Target: `Is_High_Impact` = 1 if citations >= median
- Model: Logistic Regression with balanced weights
- Evaluation: Accuracy, F1, ROC curve, threshold analysis

**Task 2: Multiclass Classification (Research Area)**
- Target: `Research area` (10 classes)
- Model: Logistic Regression (lbfgs) with balanced weights
- Evaluation: Confusion matrix, per-class ROC, C parameter tuning

---

## dataset/ -- Raw & Engineered Datasets

### professors.csv (Raw)

**317 professors**, 26 columns. Key columns:

| Column | Type | Missing | Description |
|--------|------|---------|-------------|
| `Professor` | String | 0 | Professor name |
| `University` | String | 0 | Affiliated university |
| `Rank` | String | 0 | `r1` or `r2` |
| `Research area` | String | 0 | Research specialization |
| `h_index` | Float | 11 | h-index |
| `total_citations` | Float | 11 | Total citations |
| `Email` | String | 214 | Contact email |
| `profile_url` | String | 114 | Profile URL |
| Venue columns | Integer | 0 | Per-venue paper counts (NeurIPS, ICML, etc.) |

### professors_engineered.csv (Feature-Engineered)

**317 professors**, 40 columns. Adds 14 features:

| Feature | Formula |
|---------|---------|
| `Total_Venue_Papers` | Sum of all venue paper counts |
| `Num_Distinct_Venues` | Count of distinct venues |
| `Venue_Diversity_Ratio` | Num_Distinct_Venues / 11 |
| `Citations_Per_Year` | total_citations / Num_Years |
| `H_Index_Per_Year` | h_index / Num_Years |
| `Top_Venue_Papers_Per_Year` | Papers / Num_Years |
| `Is_AI_Researcher` | 1 if AI/ML/DL/RL area |
| `Rank_Encoded` | Numeric encoding of Rank |
| `Has_Email` | 1 if email available |
| `Has_Profile_URL` | 1 if profile URL available |
| `AAAI_Dominance` | AAAI papers / Total venue papers |
| `CV_Total` | CVPR + ICCV + ECCV papers |
| `NLP_Total` | ACL + EMNLP + NAACL papers |
| `ML_Systems_Total` | NeurIPS + ICML + ICLR papers |

### Research Area Distribution

| Area | Count |
|------|-------|
| Machine Learning | 131 |
| Other | 45 |
| Artificial Intelligence | 42 |
| Computer Vision | 22 |
| Cryptography & Security | 18 |
| Deep Learning | 17 |
| NLP | 15 |
| Reinforcement Learning | 13 |
| Natural Language Processing | 10 |
| Large Language Models | 4 |

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
- Increase delay between requests

### "No data found" for a professor

- Try a more common name (common names match better)
- APIs may need time to index very recent publications
- Check the API cache in `datasets/cache/` for cached results

### Cache issues

- Delete files in `datasets/cache/*.json` to force fresh API calls
- Cache has a 7-day TTL by default

### Windows-specific: CSV encoding

The system uses `utf-8-sig` encoding for CSV output to ensure Excel compatibility on Windows. If you see garbled characters, open the CSV in Excel using Data > From Text/CSV and select UTF-8.

### Playwright not installed

If you get errors about Playwright when scraping JS-rendered sites:

```bash
playwright install chromium
```

Or skip those sites by running with `--offline` mode.

### OpenAlex rate limiting

The system handles 429 (rate limit) responses automatically:
- Waits 5 seconds and retries
- API keys provide 10x rate limit budget
- Round-robin key rotation across multiple keys
