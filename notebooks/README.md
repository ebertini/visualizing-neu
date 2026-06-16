# Notebooks

Numbered EDA notebooks. Run in order; later notebooks may import from `src/`.

| # | Notebook | Week | Purpose |
|---|---|---|---|
| 01 | `01_schema_overview.ipynb` | 1–3 | Load every raw file, print schema / nulls / samples; faculty & grant distributions; collaboration Sankey |
| 04 | `04_univariate.ipynb` | 4 | 15–20 baseline charts: grant size, duration, yearly count, agency frequency, rank & tenure distribution, co-PI rate |
| 05 | `05_temporal_trends.ipynb` | 5 | Annual & cumulative funding 2000–2025; rolling averages; college × year heatmap; agency mix; pre/post-COVID |
| 06 | `06_bivariate_segmentation.ipynb` | 6 | Agency × dept matrix; rank × award size; top-25 faculty; Gini / Lorenz concentration; tenure × agency cross-tab |
| 07 | `07_collaboration_network.ipynb` | 7 | networkx co-PI graph; degree / betweenness / PageRank; Louvain communities; cross-college collaboration matrix & trend |
| 08 | `08_topic_analysis.ipynb` | 8 | Abstract corpus QC; TF-IDF top terms; LDA 20-topic model; topic prevalence over time; topics by college; topic ↔ agency affinity |

**Rule:** never commit notebook outputs. Use `nbstripout` or "Restart kernel & clear outputs" before `git add`.

## Running order

```bash
python src/build_dataset.py  # Weeks 1-3 pipeline — generates data/processed/*.parquet
jupyter lab notebooks/04_univariate.ipynb
jupyter lab notebooks/05_temporal_trends.ipynb
jupyter lab notebooks/06_bivariate_segmentation.ipynb
jupyter lab notebooks/07_collaboration_network.ipynb
jupyter lab notebooks/08_topic_analysis.ipynb
```

## Package requirements

```bash
pip install -r requirements.txt
```

