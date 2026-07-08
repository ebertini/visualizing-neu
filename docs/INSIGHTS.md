# Northeastern Research Funding — Insights Report

Findings across all six notebooks in [`notebooks/`](../notebooks). All figures
are pulled from the current processed data (`data/processed/*.parquet`, built by
[`src/build_dataset.py`](../src/build_dataset.py)) and the artefacts in
[`outputs/`](../outputs).

**Corpus at a glance**

| Metric | Value |
|---|---:|
| Distinct faculty (HR + supplements) | 2,247 |
| Faculty who ever appear on a grant | 570 (25%) |
| Grants (deduplicated on `grant_id`) | 2,676 |
| Faculty ↔ grant links (PI + co-PI) | 3,144 |
| Grant abstracts collected | 8,075 (36.9% match to a `grant_id`) |
| Time window | 1995 – 2026 (bulk of activity 2004–2024) |
| Total awarded funding | **$2.18 B** |
| Median grant / mean grant | $412K / $816K |
| Co-PI rate on faculty–grant rows | 24.7% |

> **⚠ Attribution caveat — read this first.**
> A grant listed against a Northeastern faculty member is not always research
> *done at Northeastern* — when senior faculty join from another institution,
> their historical grants get pulled into the reporting system. The pipeline
> splits each row into three buckets via `faculty_grants.neu_status`:
>
> | Bucket | Rule (grant start relative to hire date) | Rows | $ | Counts as NEU work? |
> |---|---|---:|---:|---|
> | `earned_at_neu`     | on/after hire         | 2,098 | $1,408M (64%) | ✅ yes |
> | `prior_institution` | strictly before hire  |   866 |   $685M (31%) | ❌ no |
> | `unknown`           | dates missing         |   180 |   $153M (7%)  | ? |
>
> **NEU-work total = $1,408M (64% of the $2.18B headline).** The other 31%
> is prior-institution attribution — money the reporting system credits to
> current NEU faculty for work done at a previous employer.
>
> All headline numbers in sections 1–4 below use the **full unfiltered** dataset
> to match the shipped notebook outputs. Section 4.5 shows how the leaderboards
> shift under the earned-at-NEU filter, and the topic table in section 6.2 has
> been annotated with `% prior`. For external reports, filter to
> `neu_status == 'earned_at_neu'`.

---

## 1 · Schema & data quality (Notebook 01)

- The pipeline was reduced from 6+ overlapping tables to **4 canonical parquets**:
  `faculty`, `grants`, `faculty_grants`, `grant_abstracts`. Identifier columns
  are normalised to `faculty_id` and `grant_id`.
- **`personid` inside `grant_abstracts` is a different identifier** and does
  not join to `faculty_id`. This was the source of an earlier ranking bug (see
  Notebook 04).
- Only **36.9%** of collected abstracts match a Northeastern-side `grant_id`.
  The rest come from an external NSF/NIH crawl that includes collaborators and
  non-NU awards; topic analysis is therefore based on the ~2,848 abstracts that
  do match.

---

## 2 · Funding landscape (Notebook 02)

- Grant sizes are extremely right-skewed. Median is **$412K** but the mean is
  **~2× that** at $816K — a handful of multi-million-dollar center grants pull
  the average up.
- **Two agencies dominate**: NSF and NIH together fund **~88%** of all dollars.

  | Agency | Grants | Total $ |
  |---|---:|---:|
  | National Science Foundation | 1,686 | $1.05 B |
  | National Institutes of Health | 546 | $863 M |
  | NIH — SubAward | 105 | $76 M |
  | Office of Naval Research | 87 | $60 M |
  | HHS | 22 | $34 M |
  | Department of Energy | 37 | $34 M |

  NSF is the volume leader; **NIH grants are on average ~2.5× larger** ($1.58M
  vs $623K), reflecting the difference between single-PI NSF awards and
  multi-year NIH R01/center awards.
- ~25% of faculty–grant rows are as co-PI, so most funding still runs through
  a single lead PI. This shapes almost every downstream ranking.

---

## 3 · Funding over time (Notebook 03)

- Cumulative funding has grown from ~$100M in the early 2000s to **>$2.1 B by
  2025**. Grant counts scaled with it: from ~50/yr in 2005 to a plateau of
  **130–155 grants/yr** since 2015.
- **The peak funding year is 2018 at ~$170M** — driven by unusually large
  center awards (mean grant that year was $1.18M vs the long-run $816K).
- Post-2020 the *count* has stayed flat (~130–140/yr) but the *dollar volume*
  has drifted down (from $170M in 2018 → $85M in 2024). Interpreted as fewer
  headline center grants rather than a broad slowdown.
- Rolling-3-yr averages smooth over noise; there is no COVID-era collapse in
  the data — 2020 came in at $100M, in line with the surrounding years.

---

## 4 · Who gets funded (Notebook 04)

- **Funding is highly concentrated.** Only 570 of the 2,247 faculty ever
  appear on a grant, and among those:
  - **Gini coefficient = 0.63** (funded-faculty full-credit basis).
  - The **top 10% of funded faculty capture 48% of dollars**; the top 25 alone
    capture **~40% of the total $2.18 B**.
- **Top 10 PIs (full-credit, PI + co-PI):**

  | Faculty | College | Total $ | Grants |
  |---|---|---:|---:|
  | MELODIA, TOMMASO | Engineering | $91.4M | 40 |
  | ALSHAWABKEH, AKRAM | Engineering | $87.6M | 19 |
  | MAKRIYANNIS, ALEXANDROS | Bouvé | $62.0M | 25 |
  | LEVINE, HERBERT | Science | $47.1M | 36 |
  | LEWIS, KIM | Science | $46.2M | 21 |
  | QUARANTA, VITO | Bouvé | $45.8M | 14 |
  | WINSLOW, RAI LESTER | Engineering | $40.3M | 21 |
  | ABUR, ALI | Engineering | $38.7M | 8 |
  | KAELI, DAVID | Engineering | $33.8M | 33 |
  | BRONICH, TATIANA | Bouvé | $33.5M | 12 |

  The **PI-only vs full-credit** distinction matters: Melodia ranks #1 on
  full-credit but a different PI leads under PI-only accounting because ~15 of
  Melodia's 40 grants are as co-PI. This is documented in
  [`src/README.md`](../src/README.md).
- **Department leaderboard** — ECE and Khoury dominate by count; Pharmaceutical
  Sciences dominates on a **per-faculty** basis:

  | Department | Total $ | Grants | Faculty | $/faculty |
  |---|---:|---:|---:|---:|
  | Electrical & Computer Engineering | $451M | 456 | 64 | $7.0M |
  | Khoury College of Computer Sciences | $330M | 382 | 68 | $4.9M |
  | Physics | $275M | 290 | 43 | $6.4M |
  | **Pharmaceutical Sciences** | $255M | 137 | 16 | **$16.0M** |
  | Civil & Environmental Engineering | $170M | 149 | 22 | $7.7M |
  | Mechanical & Industrial Engineering | $162M | 219 | 45 | $3.6M |
  | Psychology | $139M | 109 | 24 | $5.8M |
  | Bioengineering | $137M | 136 | 25 | $5.5M |

  Pharm Sciences has **~2.3× the per-faculty funding of any other department**,
  driven by large NIH translational-science grants concentrated on a small
  cohort.

### 4.5 · Leaderboard shift under the earned-at-NEU filter

Recomputed with `neu_status == 'earned_at_neu'`. Full comparison table in
[notebook 04, section 6](../notebooks/04_who_gets_funded.ipynb).

- **Corpus totals:** headline $2,183M → **earned-at-NEU $1,408M (64%)**.
  Roughly 31% is prior-institution attribution; 5% is unknown.
- **Concentration rises under the filter**: Gini 0.632 → **0.653**; top-10%
  share 48% → **51%**. Prior-institution noise was flattening the curve.
- **Three top-10 headline PIs drop to $0 under earned-at-NEU** (Quaranta,
  Winslow, Bronich — all pre-hire). **Levine** shrinks ~88% ($47M → $6M).
  All four are senior hires from 2019–2024.
- **Corrected top 10 by earned-at-NEU funding:**

  | Faculty | College | Earned-at-NEU $ | Grants |
  |---|---|---:|---:|
  | MELODIA, TOMMASO | Engineering | $88.9M | 30 |
  | ALSHAWABKEH, AKRAM | Engineering | $87.6M | 19 |
  | MAKRIYANNIS, ALEXANDROS | Bouvé | $59.5M | 24 |
  | LEWIS, KIM | Science | $46.2M | 21 |
  | ABUR, ALI | Engineering | $38.7M | 7 |
  | KAELI, DAVID | Engineering | $33.8M | 33 |
  | BUSNAINA, AHMED | Engineering | $30.5M | 13 |
  | TORCHILIN, VLADIMIR | Bouvé | $29.0M | 15 |
  | CHOFFNES, DAVID | Khoury | $22.2M | 14 |
  | WILSON, CHRISTO | Khoury | $19.8M | 8 |

  Choffnes, Wilson, Lazer, and Amiji enter the top-15 under this view — these
  are researchers who built their funding *at* NEU and were being crowded out
  of the headline list by imported historical totals.

---

## 5 · Collaboration network (Notebook 05)

- Co-PI graph: **287 connected faculty, 504 edges**. Most faculty are
  disconnected — the graph covers only the ~half of funded PIs who ever share
  a grant.
- Edge weights (total $ shared on joint grants) are dominated by a small
  cluster inside Engineering + Khoury. **Cross-college co-PI links** are the
  minority but they carry disproportionate dollar volume — Engineering ↔
  Science and Engineering ↔ Bouvé links tend to be on multi-PI center awards.
- The network has grown steadily since ~2010 (see
  [`outputs/w7_collab_over_time.png`](../outputs/w7_collab_over_time.png)) —
  consistent with the university's push toward interdisciplinary institutes.
- **Betweenness is near zero for almost every node** because the graph is
  fragmented into many small components; there is no single "bridge" PI
  connecting the whole faculty.

---

## 6 · Research topics (Notebook 06)

An 8-topic LDA model was fitted on **1,909 grants that have both a match to
`grants.parquet` and non-trivial abstract text** (NSF boilerplate + HTML
residue removed, min 40 tokens, `min_df=15`, `max_df=0.6`, bigrams on).
Topic labels were assigned by inspection of the top terms per topic.

### 6.1 Model quality

- **Assignment confidence**: mean top-topic probability **0.68** (std 0.18).
  **78%** of grants have their top topic at ≥0.5 confidence, meaning most
  documents are dominated by a single theme rather than being genuine mixtures.
- **k=8** was chosen from a perplexity sweep over k ∈ {5…12}; 8 sits at the
  elbow. Notable: biomedical splits cleanly into two — a drug/disease/cancer
  cluster and a cell/molecular-biology cluster — and the CS-side splits into
  a "software/data/ML systems" bucket and a "hardware/energy/wireless
  systems" bucket rather than the older cybersecurity/wireless separation.

### 6.2 The eight topics — funding breakdown

Grants deduplicated on `grant_id` after joining to the LDA assignments
(N = 1,909 grants with a matched abstract). **Earned-at-NEU $** is the slice
of the headline **Total $** that passes the `neu_status == 'earned_at_neu'`
filter; **% prior** is the complementary share attributed to work done at the
PI's previous institution.

| Topic | Grants | Total $ | Earned-at-NEU $ | % prior | Avg grant |
|---|---:|---:|---:|---:|---:|
| **Biomedical (drug/disease/cancer)** | 364 | **$456M** | $259M | 43% | $1.25M |
| Software, data & ML systems | 436 | $448M | $281M | 37% | $1.03M |
| Hardware, energy & wireless systems | 296 | $251M | $204M | **19%** | $847K |
| Cell & molecular biology | 269 | $176M | $83M | **53%** | $656K |
| Environmental & public health | 246 | $135M | $81M | 40% | $547K |
| STEM education & outreach | 126 | $106M | $58M | 45% | $841K |
| HCI, learning & applied research | 35 | $28M | $21M | 25% | $801K |
| Mathematics & theoretical physics | 137 | $17M | $11M | 35% | $122K |

**Key takeaways:**

- **Biomedical (drug/disease/cancer) is #1 by dollars on both views** — large
  NIH R01/center awards drive the ~$1.25M average grant. But 43% is prior
  institution: the recent Bouvé senior hires whose historical NIH grants are
  being counted at NEU.
- **Software / data / ML is essentially co-#1** at $448M — the CS-heavy modern
  successor to the old "cybersecurity" label. Cleaner NEU story than
  biomedical (only 37% prior).
- **Hardware / energy / wireless is the "most genuinely NEU" bucket** — only
  19% prior. Built around long-tenured ECE faculty (Melodia, Alshawabkeh)
  who won their grants while at NEU.
- **Cell & molecular biology has the highest prior-institution share (53%)** —
  a lot of imported historical NIH work sits here.
- **Mathematics & theoretical physics** is smallest on $ (137 grants but only
  $17M total, $122K average). Basic-science awards are genuinely cheaper.

### 6.3 Topic mix has shifted over time

Comparing 2005–2014 vs 2015–2024 share of grants, restricted to **earned-at-NEU
grants only** (`neu_status == 'earned_at_neu'`). Using earned-at-NEU here
rather than all grants strips out prior-institution history that would
otherwise distort the trend.

| Topic | Early share | Late share | Δ |
|---|---:|---:|---:|
| Software, data & ML systems | 17.9% | 25.6% | **+7.7** |
| Environmental & public health | 9.6% | 15.9% | **+6.3** |
| Hardware, energy & wireless systems | 14.1% | 18.6% | +4.5 |
| Mathematics & theoretical physics | 6.8% | 5.7% | −1.1 |
| STEM education & outreach | 8.1% | 5.5% | −2.6 |
| HCI, learning & applied research | 3.8% | 1.0% | −2.8 |
| Biomedical (drug/disease/cancer) | 21.4% | 15.9% | −5.5 |
| Cell & molecular biology | 18.4% | 11.9% | **−6.5** |

Grant counts: 397 in the early window, 706 in the late window (out of 1,103
earned-at-NEU grants with matched abstracts).

- **Software / data / ML is the biggest riser** at +7.7 points — the CS-side
  growth engine of the last decade, aligned with Khoury's headcount growth.
- **Environmental & public health is the second biggest riser** at +6.3 points,
  driven by post-2015 NSF sustainability and climate solicitations.
- **Cell & molecular biology dropped 6.5 points** as a share of new grants —
  the biggest faller. Combined with the drug/disease drop (−5.5), the *overall*
  biomedical footprint at NEU is falling as a share of new grant volume,
  though dollar totals remain high because remaining biomedical grants are
  larger.
- **HCI, learning & applied research is tiny and shrinking** (−2.8) — may
  reflect an under-fit topic rather than a real research decline; only 35
  grants total.

### 6.4 Topic × college / agency signals

(See [`notebooks/figures/w6_*.png`](../notebooks/figures/) and
[`outputs/w8_topic_by_college.png`](../outputs/w8_topic_by_college.png).)

- **Biomedical (drug/disease/cancer)** and **Cell & molecular biology** are
  Bouvé + CoS heavy.
- **Software / data / ML** is Khoury-dominated, with some CoS (physics,
  math) and CoE (ECE) contribution.
- **Hardware / energy / wireless systems** is ECE / MIE heavy (CoE-dominated).
- **Environmental & public health** cuts across CoE (Civil/Environmental),
  CoS (Marine Sciences), and Bouvé (public health).
- **Agency-topic affinity** is stark: NIH funds ~80% of the biomedical
  topics; NSF funds ~90% of software/data/ML and STEM-ed; DoD (ONR/ARO/AFRL)
  is concentrated in Hardware/energy/wireless and Materials.

---

## Cross-notebook themes

1. **Concentration is the dominant story.** By dollars, by PIs, by
   departments, and by topics — a small tail carries most of the total. Gini
   0.63 on funded faculty, top-10% capture 48%, one department (Pharm
   Sciences) has 2.3× the per-faculty $ of any other.

2. **NSF vs NIH are two different funding *modes*, not two competitors.**
   NSF = many small single-PI grants across CS, STEM-ed, and basic science.
   NIH = few large multi-year center awards concentrated in Biomedical and
   Neuro. Ignoring this split makes trend analysis look noisier than it is.

3. **The center-grant era peaked around 2018.** Grant *counts* are steady but
   *dollar volume* has drifted down since — driven almost entirely by fewer
   very-large awards, not by broad-based decline.

4. **PI-only vs full-credit accounting materially changes rankings.**
   Documented in [`src/README.md`](../src/README.md) with a worked example.
   Any external report should state which credit model it uses.

5. **The abstract corpus is a partial view.** ~63% of the 8,075 abstracts do
   not match a Northeastern grant_id, so topic-level dollar totals are
   under-counted for topics where NU faculty are frequent co-PIs on external
   awards (notably Environmental and Wireless).

---

## Where the numbers live

| Result | File |
|---|---|
| Annual grant/$ totals + rolling averages | [`outputs/annual_grant_summary.csv`](../outputs/annual_grant_summary.csv) |
| Top-25 faculty (PI + co-PI, full credit) | [`outputs/top_faculty_funding.csv`](../outputs/top_faculty_funding.csv) |
| Top-15 departments | [`outputs/top_dept_funding.csv`](../outputs/top_dept_funding.csv) |
| Co-PI pairs + weighted edges | [`outputs/collab_pairs.csv`](../outputs/collab_pairs.csv), [`outputs/collab_edges.csv`](../outputs/collab_edges.csv) |
| Network centrality per faculty | [`outputs/network_node_metrics.csv`](../outputs/network_node_metrics.csv) |
| Per-abstract topic assignment (k=8) | [`outputs/topic_assignments.csv`](../outputs/topic_assignments.csv) |
| Static figures | [`outputs/w4_*.png`](../outputs/) … `w8_*.png` and [`notebooks/figures/`](../notebooks/figures/) |

---

## 7 · Follow-up deep dive (Notebook 07)

All produced in [`notebooks/07_topic_deep_dive.ipynb`](../notebooks/07_topic_deep_dive.ipynb).

### The PI's questions

> 1. The current topics are quite high-level. What kind of research do we do
>    within each area that characterizes where we are strong at NEU? For
>    example, within biomedical and cell biology, what do we do? What are we
>    good at?
> 2. Maybe you can try to apply hierarchical topic modeling to see what we get?
> 3. One interesting thing to try is creating an interactive projection of all
>    the grants (maybe with UMAP?) to see how they cluster. Then we can use
>    color and other features to see how topics and colleges are distributed in
>    the projection. Does it make sense to you?
> 4. Similarly, what kind of research does every college do? I know you started
>    this, but I can't see the topic labels, so I can't really interpret it.

### How each question was addressed in Notebook 07

| # | Question | Section | Method |
|---|---|---|---|
| 1 | What's inside each parent topic? | §2 sub-topics | Refit LDA (k=4) inside each of the 8 parent topics; export top terms, top faculty, top grants → [`outputs/subtopics.csv`](../outputs/subtopics.csv) |
| 2 | Hierarchical view? | §3 dendrogram | Jensen–Shannon distance between the 8 topic word-distributions + average linkage → [`outputs/w7_topic_dendrogram.png`](../outputs/w7_topic_dendrogram.png) |
| 3 | Interactive UMAP projection? | §4 UMAP | TF-IDF → cosine UMAP over 2,848 abstracts, both static 4-panel and Plotly interactive → [`docs/07_grant_projection.html`](07_grant_projection.html) |
| 4 | Readable "what each college does"? | §1 heatmap + cards | Row-normalised topic × college heatmap with full labels + per-college profile cards → [`docs/college_profiles.html`](college_profiles.html) |

### 7.1 What each college works on (row-normalised)

The heatmap in [`outputs/w7_topic_by_college_rownorm.png`](../outputs/w7_topic_by_college_rownorm.png)
is row-normalised: **each row sums to 100%**, so it directly reads as *"of all
grants at this college, what fraction fall in each topic?"* Highlights:

- **College of Engineering** — Wireless networks & sensing dominates (~25%),
  followed by Materials/mechanical and STEM-ed. NSF-heavy.
- **Khoury** — Cybersecurity & software systems (~40%+), with Neuro & behavioral
  (via HCI / ML on people) and STEM-ed rounding out the top 3.
- **College of Science** — Materials/mechanical is #1, then Environmental and
  Biomedical. NSF-heavy.
- **Bouvé** — Biomedical & cell biology is #1 by a wide margin, then Neuro &
  behavioral, then STEM-ed. The only college where **NIH** is the top agency.
- **CSSH** — Environmental & public health leads (climate policy, public
  health), followed by STEM-ed and Cybersecurity (privacy/social side).
- **CAMD** — Neuro & behavioral (perception, HCI) plus Environmental.
- **D'Amore-McKim** and **School of Law** are small (10–12 grants each), with
  Cybersecurity and Environmental respectively as top themes.

Per-college profile cards with faculty leaderboards are in
[`outputs/college_profiles.csv`](../outputs/college_profiles.csv) and the
rendered [`docs/college_profiles.html`](college_profiles.html).

### 7.2 Sub-topics inside each parent topic

For each of the 8 parent topics we refit **LDA at k=4** on just its documents,
so "Biomedical" becomes 4 concrete sub-themes. Full table in
[`outputs/subtopics.csv`](../outputs/subtopics.csv). Labels are auto-generated
from the top 3 terms and should be curated by hand after inspection. Highlights:

| Parent | Sub-theme (top terms) | Grants | $ |
|---|---|---:|---:|
| Biomedical & cell biology | drug · cancer · tumor | 125 | $219M |
| Biomedical & cell biology | cell · cells · tissue | 236 | $196M |
| Biomedical & cell biology | brain · development · changes | 79 | $107M |
| Cybersecurity & software systems | software · network · security | 388 | $221M |
| Cybersecurity & software systems | spectrum · wireless · thz | 29 | $66M |
| Cybersecurity & software systems | privacy · infrastructure · social | 34 | $62M |
| Materials & mechanical/chemical | materials · energy · properties | 162 | $120M |
| Materials & mechanical/chemical | spin · devices · magnetic | 64 | $49M |
| Environmental & public health | health · social · community | 197 | $137M |
| Environmental & public health | marine · environmental · climate | 146 | $83M |
| Neuro & behavioral science | control · learning · algorithms | 178 | $112M |
| Neuro & behavioral science | brain · neural · children | 56 | $77M |
| STEM education & outreach | science · university · program | 251 | $254M |
| STEM education & outreach | program · reu · northeastern | 25 | $32M |
| Mathematics & theoretical physics | physics · higgs · particle | 22 | $30M |
| Mathematics & theoretical physics | geometry · quantum · algebras | 85 | $10M |

**What this tells us:**

- Northeastern's **biomedical strength splits cleanly between drug/cancer
  therapeutics and cell biology**, with a smaller neuroscience-adjacent slice.
  These are two distinct funding profiles even inside one parent topic.
- **Cybersecurity is dominated by a huge "software / network / security"
  bucket** ($221M, 388 grants) — the tail (privacy, THz wireless) is where the
  differentiated NEU work lives.
- The **"marine / environmental / climate"** sub-topic in Environmental & public
  health is a distinct, sizeable ($83M) cluster — worth calling out separately
  in reports rather than lumping into a generic "environment" bucket.
- The **STEM-ed topic is really an "outreach + REU + program evaluation"**
  bucket — most of its dollars go to education infrastructure grants, not
  research.

### 7.3 Topic dendrogram (Jensen–Shannon distance)

[`outputs/w7_topic_dendrogram.png`](../outputs/w7_topic_dendrogram.png) clusters
the 8 parent topics by JS distance between their word distributions. The tree
shows three natural super-groups:

1. **Life sciences** — Biomedical & cell biology cluster with Neuro & behavioral
   at the lowest cut.
2. **Engineering / systems** — Wireless networks & sensing pair with Cybersecurity
   & software systems; Materials/mechanical joins next.
3. **Everything else** — Environmental & public health, STEM-ed, and Math /
   theoretical physics sit as three loose leaves.

Practical read: if you were to compress k=8 down to **k=3–4 super-topics** for
an exec summary, the natural cuts are life-sciences, engineering-systems,
environment+policy, and basic-science/education.

### 7.4 UMAP projection

Two independent projections of the same 2,848 abstracts are provided so we
can cross-check the topic structure.

**TF-IDF baseline** (fast, simple, deterministic):
- Static 2×2 panel: [`outputs/w7_umap_grants.png`](../outputs/w7_umap_grants.png).
  Coloured by topic, college, agency, and year × $.
- Interactive Plotly HTML: [`docs/07_grant_projection.html`](07_grant_projection.html)
  — 2,848 abstracts, hover for title / PI / agency / $ / year, buttons to
  toggle colour between topic, college, and agency.

**SPECTER2 embedding** ([`allenai/specter2_base`](https://huggingface.co/allenai/specter2_base)
+ proximity adapter — a bert-base transformer trained on 6M citation-linked
scientific-paper triplets):
- Static 2×2 panel: [`outputs/w7_umap_grants_specter2.png`](../outputs/w7_umap_grants_specter2.png).
- Interactive Plotly HTML: [`docs/07_grant_projection_specter2.html`](07_grant_projection_specter2.html).
- Precompute script: [`src/build_specter2_embeddings.py`](../src/build_specter2_embeddings.py)
  — ~8 min on CPU (one-time), cached to `data/processed/specter2_embeddings.npy`.

**What comparing the two tells us:**

- The SPECTER2 layout is **visibly more structured**. LDA topic colours form
  tighter, more separated blobs (Math sits as an isolated island top-left,
  Cybersecurity forms a coherent block at top, Materials/mechanical clusters
  tightly at left, Neuro is a distinct upper-middle group). The TF-IDF layout
  is one large central blob with only partial topic separation.
- This is **independent validation** of the k=8 LDA topics: two totally
  different similarity signals (surface vocabulary vs. citation-based semantic
  embedding) both group the same abstracts into recognisably similar clusters.
- SPECTER2 also reveals **finer sub-structure inside parents** — the drug /
  cell-biology / brain sub-clusters inside Biomedical are visually distinct,
  matching the sub-topic table in section 7.2. This is the projection to send
  the PI for actual exploration.
- The TF-IDF version is kept as a cheap sanity check and because it needs no
  model download; SPECTER2 is the "publication-grade" version.

The 2-D layout also confirms the dendrogram: the biomedical + neuro cluster
and the cyber + wireless cluster occupy opposite ends, with STEM-ed forming a
distinct island in the middle.

Cleaned abstract text (2,848 docs)
        │
        ▼
   TfidfVectorizer(max_df=0.6, min_df=5,
                   ngram_range=(1,2),
                   max_features=15000)
        │
        ▼
Sparse TF-IDF matrix   →   shape ≈ (2,848 × 15,000)
Each abstract is a 15,000-D vector of term weights.
        │
        ▼
   UMAP(n_neighbors=15, min_dist=0.1,
        metric='cosine', n_components=2)
        │
        ▼
   2-D embedding  →  shape (2,848 × 2)   ← this is what's plotted

### Deliverables from this section

| Artefact | File |
|---|---|
| Row-normalised topic × college heatmap | [`outputs/w7_topic_by_college_rownorm.png`](../outputs/w7_topic_by_college_rownorm.png) |
| Per-college profile cards (data) | [`outputs/college_profiles.csv`](../outputs/college_profiles.csv) |
| Per-college profile cards (rendered) | [`docs/college_profiles.html`](college_profiles.html) |
| 32 sub-topics (8 parents × 4) | [`outputs/subtopics.csv`](../outputs/subtopics.csv) |
| Topic dendrogram | [`outputs/w7_topic_dendrogram.png`](../outputs/w7_topic_dendrogram.png) |
| UMAP static 2×2 panel (TF-IDF) | [`outputs/w7_umap_grants.png`](../outputs/w7_umap_grants.png) |
| UMAP interactive projection (TF-IDF) | [`docs/07_grant_projection.html`](07_grant_projection.html) |
| UMAP static 2×2 panel (SPECTER2) | [`outputs/w7_umap_grants_specter2.png`](../outputs/w7_umap_grants_specter2.png) |
| UMAP interactive projection (SPECTER2) | [`docs/07_grant_projection_specter2.html`](07_grant_projection_specter2.html) |
| SPECTER2 embedding cache (768-D × 8,075) | `data/processed/specter2_embeddings.npy` |

---

## 8 · Open questions for the PI

A few high-level decisions from you would materially sharpen the next pass of
Notebook 07 and the report that comes out of it.

1. **Who is the audience for the final report — executives or planners?**
   The dendrogram suggests a natural collapse to **3–4 super-topics**
   (life-sciences, engineering-systems, environment/policy, basic-science).
   An exec deck wants that. Internal planning wants the full 8, or even the
   32 sub-topics. Pick one default and we shape the rest of the report
   around it.

2. **What time window defines "current" NEU strengths?** The corpus spans
   1995–2026. Reporting on the full window emphasises historical peaks
   (2018 center grants); reporting on the last 5–10 years emphasises where
   NEU is going. The "biomedical dropped 7.5 points" and "environmental
   rising" findings swing heavily on this choice.

3. **Should center grants be separated from steady-state faculty funding?**
   A handful of $10M+ awards drive several of the topic and department
   totals. An appendix that names them explicitly would prevent the reader
   from mistaking one-off wins for structural strengths.

4. **How do we want to credit multi-PI grants?** A $10M grant with a lead PI
   and two co-PIs can be counted three different ways, and the choice
   materially changes the leaderboard:

   - **Full-credit (current default)** — every named investigator gets the
     full $10M. Simple, but the same dollars are counted 3× across faculty,
     so college and department totals do not sum to the corpus total.
   - **PI-only** — only the lead PI gets the $10M; co-PIs get $0. Matches
     how the government thinks of the award, but makes co-PI-heavy roles
     (bridge builders, junior faculty on senior PIs' grants) invisible.
   - **Fractional** — the $10M is split evenly across the three
     investigators, so each gets ~$3.3M. Sums correctly and doesn't reward
     name-only listing, but distorts when the "co-PI" is really a full
     partner or when they're really peripheral.

   Concrete effect on the current top-10 leaderboard (full-credit view):

   | Faculty | Full-credit | PI-only | Δ |
   |---|---:|---:|---:|
   | MELODIA, TOMMASO | $91.4M | $77.1M | −16% (15 of 40 grants as co-PI) |
   | ALSHAWABKEH, AKRAM | $87.6M | $85.7M | −2% (almost always lead) |
   | LEVINE, HERBERT | $47.1M | *drops out of top 10* | most funding as co-PI |
   | KAELI, DAVID | $33.8M | *drops out of top 10* | ~half of grants as co-PI |
   | ABUR, ALI | $38.7M | *drops out of top 10* | mostly co-PI on center grants |
   | BARRETT, LISA | *not in top 10* | enters at $22.4M | almost always lead PI |

   **Under PI-only the ordering flips**: Alshawabkeh moves ahead of Melodia,
   and four names in the current top-10 (Levine, Kaeli, Abur, Bronich) drop
   out entirely, replaced by lead-PI-heavy researchers like Barrett. Under
   fractional the top-10 barely changes because most of those top grants
   are single-PI, but department totals sum correctly.

   External-facing reports need one canonical rule so the same faculty
   member doesn't appear with three different funding totals in three
   different documents. Recommendation on my end: **full-credit for
   department- and college-level narratives** (it reflects who was involved),
   **PI-only for the individual PI leaderboard** (it reflects who won the
   grant), and never mix.

5. **Should we invest a session in curating the 32 sub-topic labels
   together?** Right now they are honest but ugly ("drug · cancer · tumor").
   30 minutes with you looking at the top-terms table would turn them into
   the readable phrases you'd actually want on a slide.

Items 1–4 are the ones that change *what the report says*; item 5 changes
*how it reads*.
