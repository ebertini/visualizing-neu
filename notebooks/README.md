# Notebooks

Numbered EDA notebooks. Run in order; later notebooks may import from `src/`.

| # | Notebook | Week | Purpose |
|---|---|---|---|
| 01 | `01_schema_overview.ipynb` | 1 | Load every raw file, print schema / nulls / samples |
| 02 | _Week 2_ | 2 | Data quality audit |
| 03 | _Week 3_ | 3 | Unified data model build |

**Rule:** never commit notebook outputs. Use `nbstripout` or "Restart kernel & clear outputs" before `git add`.
