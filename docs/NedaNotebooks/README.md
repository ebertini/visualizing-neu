# Northeastern University Research Funding Analysis

Exploratory data analysis of externally funded research grants at Northeastern University from 1995 to 2026.

## Goal
Build a picture of who is funded at Northeastern, how much, by whom, and on what topics, and how that has changed over time.

## Data
Four internal datasets:
- `faculty-list-2025.xlsx` — current faculty roster (2,232 people)
- `grants-with-coPI.xlsx` — primary grant file, 2,002 unique grants after filtering
- `grants-with-abstract.xlsx` — grant titles and abstracts (8,075 rows, 2,873 with abstract text)
- `ri_matches_grants_2026.xlsx` — alternate grant export, used for cross-validation only

Place all data files in a `data/` folder in the project root.

## Notebooks
Run in order:
- `01_northeastern_funding_basic_QC.ipynb` — data loading, cleaning, null audit, and exploratory analysis
- `02_funding_analysis.ipynb` — funding concentration, college and agency breakdowns, co-PI structure, gap analysis
- `03_topic_modeling.ipynb` — text cleaning and topic modeling with LDA, NMF, and BERTopic on grant abstracts
- `04_topic_validation.ipynb` — topic coherence, assignment confidence, classifier, UMAP, within-topic analysis, college-topic cross-analysis

## Requirements
```bash
pip install pandas numpy matplotlib scikit-learn nltk adjustText
```

For topic modeling (notebook 03 and 04):
```bash
pip install bertopic sentence-transformers umap-learn hdbscan kaleido==0.2.1
```

After installing nltk, run once in Python:
```python
import nltk
nltk.download('wordnet')
nltk.download('omw-1.4')
```

## Environment
Developed with Python 3.10 on macOS (Apple Silicon). Tested in a conda environment.

## Status
Data cleaning complete. Funding analysis complete. Topic modeling complete. Topic validation and college-topic analysis complete.