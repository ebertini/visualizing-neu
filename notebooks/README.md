# Notebooks

Numbered EDA notebooks. Run in order — later notebooks depend on the Parquet files
produced by [../src/build_dataset.py](../src/build_dataset.py).

| # | Notebook | What it covers |
|---|---|---|
| 01 | [01_schema_overview.ipynb](01_schema_overview.ipynb) | Load every processed table, print schemas / nulls / samples; sanity-check the faculty ↔ grants ↔ abstracts joins. |
| 02 | [02_funding_landscape.ipynb](02_funding_landscape.ipynb) | Baseline distributions: grant size (linear + log), duration, yearly count, agency frequency, faculty rank & tenure, co-PI rate. |
| 03 | [03_funding_over_time.ipynb](03_funding_over_time.ipynb) | Annual & cumulative funding 2000–2025, rolling averages, college × year heatmap, agency mix over time, pre/post-COVID comparison. |
| 04 | [04_who_gets_funded.ipynb](04_who_gets_funded.ipynb) | Concentration analysis: Lorenz curve / Gini, top-25 faculty, top-15 departments, agency × department matrix, rank × award-size 3-panel. |
| 05 | [05_collaboration_network.ipynb](05_collaboration_network.ipynb) | Co-PI network: NetworkX graph, degree / betweenness / PageRank centrality, Louvain communities, cross-college collaboration matrix, trend over time. |
| 06 | [06_research_topics.ipynb](06_research_topics.ipynb) | Topic model over grant abstracts: LDA (k=8), coherence & confidence validation, topic prevalence + trends over time, topics × college / agency / funding, top faculty per topic. |

**Rule:** never commit notebook outputs. Use `nbstripout` or "Restart kernel & clear
outputs" before `git add`.

## Running order

```bash
# 1. (Re)build the processed Parquet files
python src/build_dataset.py

# 2. Open and run notebooks in order
jupyter lab notebooks/01_schema_overview.ipynb
jupyter lab notebooks/02_funding_landscape.ipynb
jupyter lab notebooks/03_funding_over_time.ipynb
jupyter lab notebooks/04_who_gets_funded.ipynb
jupyter lab notebooks/05_collaboration_network.ipynb
jupyter lab notebooks/06_research_topics.ipynb
```

## Package requirements

```bash
pip install -r requirements.txt
```

## Schema at a glance

All notebooks load their data from `../data/processed/` — see
[../src/README.md](../src/README.md) for the full column reference. Key join keys:

- `faculty.parquet.faculty_id` = `faculty_grants.faculty_id` = `ClientFacultyId` in raw grants
- `grants.parquet.grant_id`   = `faculty_grants.grant_id`
- Abstracts join to grants via `grant_abstracts.sourceactivityid` = `grants.grant_id`
  (~37% match rate — see notebook 06 for handling).
- **`grant_abstracts.personid` is a DIFFERENT identifier** and does not join to `faculty_id`.
