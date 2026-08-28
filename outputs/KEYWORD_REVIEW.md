# Keyword-Topic Review Sheet (source: draft)


## 0. Commands + time estimate

```bash
cp outputs/keyword_topics.draft.json outputs/topic_keywords.json
$EDITOR outputs/topic_keywords.json        # ~60-90 min required tier, see below
python3 -m src.kw_curation --check         # exit 1 until genuinely curated
python3 -m src.kw_review_sheet --from curated   # proofread your own edits
```

**Required tier (~60-90 min):** parent labels + accept/reject (~10 min), leaf
labels + accept/reject (~40 min), and only the terms flagged in §3 below
(expect ~15-20% of all terms) — sorted flagged-first with a
`— trust below this line —` separator once you're inside a leaf's keyword
list. If the flagged fraction feels like it's ballooned past ~35%, that's a
signal to tighten the discovery parameters and regenerate rather than review
harder.


## 1. Does this even work? (coverage — read this first)

- Full harvested vocabulary: **12776 terms**, of which
  **29 grants** have zero matching
  candidate terms at all (the irreducible floor — genuinely text-less docs).
- Pruned to **2506 terms** (2500 by rank +
  6 backfilled): **29 grants**
  still match zero terms — equal to the floor above, by construction (verified by
  an assert in kw_vocab_discover.py).
- Parent clustering: k=9
  (silhouette=0.1418); leaf clustering:
  k=25 (silhouette=0.1241).
- Nesting check: **0 leaf clusters
  span more than one parent** (should be 0 — Plan B guarantees this by construction).
- ARI (doc-centroid grouping vs. full c-TF-IDF-loading grouping):
  **0.1353** — low means the semantic
  grouping is adding real information beyond simple topic co-occurrence, which is
  what you want to see.


## 2. Candidate parent groups

### P1 — 668 terms (26.7%)
- Top terms: biochemical, molecular, in vivo, cellular, therapeutic, signaling, cell, in vitro, proteins, binding, expression, diseases
- Contributing legacy topics: topic 11 (concentration=21.155, n=1227), topic 22 (concentration=18.257, n=639), topic 23 (concentration=14.156, n=453)

### P8 — 631 terms (25.2%)
- Top terms: solutions, deployment, deployed, hardware, algorithms, reliable, rely, develops, performance, architecture, practical, enabling
- Contributing legacy topics: topic 7 (concentration=15.356, n=1336), topic 3 (concentration=10.172, n=1302), topic 19 (concentration=9.463, n=388)

### P4 — 454 terms (18.1%)
- Top terms: academic, national, institutions, participation, community, leadership, nsf, universities, professional, scholars, researchers, institutional
- Contributing legacy topics: topic 26 (concentration=19.517, n=566), topic 13 (concentration=10.784, n=550), topic 10 (concentration=9.838, n=728)

### P2 — 310 terms (12.4%)
- Top terms: evidence, age, findings, population, behavioral, interventions, adults, whether, examine, mental, differences, longitudinal
- Contributing legacy topics: topic 6 (concentration=11.73, n=1044), topic 1 (concentration=11.134, n=1492), topic 29 (concentration=6.182, n=136)

### P5 — 178 terms (7.1%)
- Top terms: materials, temperature, thermal, outreach, high school, fundamental, dissipation, films, undergraduate, energy, thin, wave
- Contributing legacy topics: topic 0 (concentration=9.796, n=2635), topic 24 (concentration=4.938, n=158), topic 2 (concentration=1.535, n=198)

### P3 — 135 terms (5.4%)
- Top terms: coastal, sediment, coast, ecology, environmental, river, ecological, nutrient, wetlands, climate change, ecosystem services, climate
- Contributing legacy topics: topic 4 (concentration=11.961, n=1232), topic 16 (concentration=4.667, n=224), topic 24 (concentration=0.531, n=17)

### P6 — 125 terms (5.0%)
- Top terms: string theory, representation theory, algebraic, symmetry, areas of mathematics, algebras, quantum groups, integrable systems, invariants, algebraic geometry, combinatorics, mathematicians
- Contributing legacy topics: topic 2 (concentration=14.899, n=1922), topic 0 (concentration=1.249, n=336), topic 4 (concentration=0.214, n=22)

### P9 — 3 terms (0.1%)
- Top terms: timing, disruption, tracing
- Contributing legacy topics: topic 2 (concentration=0.054, n=7), topic 18 (concentration=0.047, n=2), topic 3 (concentration=0.039, n=5)

### P7 — 2 terms (0.1%)
- Top terms: higher, ap
- Contributing legacy topics: topic 2 (concentration=0.124, n=16), topic 7 (concentration=0.023, n=2)


## 3. Flagged terms needing disambiguation (1326/2506 = 52.9%) — the most valuable page

— review these; everything else can be skimmed —

- `10` — low precision (0.2553)
- `12` — low precision (0.3333)
- `12 months` — low precision (0.2857)
- `15` — low precision (0.2581)
- `20` — low precision (0.3051)
- `2012` — low precision (0.2353)
- `2013` — low precision (0.2)
- `2014` — low precision (0.2143)
- `2016` — low precision (0.2353)
- `2017` — low precision (0.1364)
- `2018` — low precision (0.1923)
- `2019` — low precision (0.1818)
- `2020` — low precision (0.3103)
- `2023` — low precision (0.2308)
- `25` — low precision (0.2692)
- `2d` — low precision (0.3478)
- `3` — low precision (0.2566); high df (678)
- `3-d` — low precision (0.2667)
- `3d` — low precision (0.2184)
- `4` — low precision (0.2297); high df (283)
- `5` — low precision (0.271); high df (155)
- `50` — low precision (0.2222)
- `6` — low precision (0.2526)
- `9` — low precision (0.32)
- `aberrant` — low precision (0.2222)
- `ability` — low precision (0.3198); high df (369)
- `about` — low precision (0.2729); high df (469)
- `abroad` — low precision (0.25)
- `absorption` — low precision (0.3077)
- `abstraction` — low precision (0.3333)
- `academia` — low precision (0.2698)
- `academic` — low precision (0.2532); high df (154)
- `accelerate` — low precision (0.2083)
- `access` — low precision (0.314); high df (242)
- `accomplish` — low precision (0.3134)
- `accurate` — low precision (0.3235)
- `achieve` — low precision (0.2881); high df (243)
- `acid` — low precision (0.2955)
- `acquisition` — low precision (0.25)
- `acting` — low precision (0.25)
- `action` — low precision (0.1667)
- `activation` — low precision (0.2394)
- `active` — low precision (0.2564); high df (195)
- `activities` — low precision (0.2035); high df (462)
- `acute` — low precision (0.3235)
- `adaptation` — low precision (0.2414)
- `adaptive` — low precision (0.2333)
- `addition` — low precision (0.2594); high df (397)
- `address` — low precision (0.2961); high df (466)
- `addressing` — low precision (0.2164)
- `adjusted` — low precision (0.25)
- `administration` — low precision (0.3158)
- `adults` — low precision (0.3444)
- `advance` — low precision (0.2626); high df (297)
- `advanced` — low precision (0.2977); high df (309)
- `advancing` — low precision (0.2364)
- `adversaries` — low precision (0.2941)
- `advisory` — low precision (0.3261)
- `affect` — low precision (0.2313); high df (160)
- `after` — low precision (0.2437); high df (197)
- `against` — low precision (0.2763); high df (152)
- `age` — low precision (0.24)
- `agencies` — low precision (0.2951)
- `agents` — low precision (0.2759)
- `aging` — low precision (0.2727)
- `aim 1` — low precision (0.1986)
- `aim 2` — low precision (0.2014)
- `aim 3` — low precision (0.1731)
- `algorithms` — low precision (0.3115); high df (305)
- `algorithmic` — low precision (0.3043)
- `all` — low precision (0.2496); high df (581)
- `alliance` — low precision (0.3125)
- `allocation` — low precision (0.2353)
- `allow` — low precision (0.3037); high df (349)
- `allowing` — low precision (0.2593)
- `along` — low precision (0.2216); high df (167)
- `altered` — low precision (0.2273)
- `alternative` — low precision (0.2952)
- `american` — low precision (0.3187)
- `analyses` — low precision (0.2524)
- `analysis` — low precision (0.2837); high df (557)
- `analytical` — low precision (0.2386)
- `anatomical` — low precision (0.2857)
- `animal` — low precision (0.1954)
- `annotations` — low precision (0.3333)
- `annual` — low precision (0.2656)
- `another` — low precision (0.2128)
- `any` — low precision (0.2793); high df (179)
- `ap` — low precision (0.2)
- `applicable` — low precision (0.3286)
- `applicant` — low precision (0.2099); high df (262)
- `application-specific` — low precision (0.2857)
- `approaches` — low precision (0.2466); high df (446)
- `approximately` — low precision (0.2692)
- `architecture` — low precision (0.3273)
- `arise` — low precision (0.1957)
- `around` — low precision (0.2759)
- `array` — low precision (0.2588)
- `articles` — low precision (0.2963)
- `artifacts` — low precision (0.3214)
- `arts` — low precision (0.1538)
- `assembly` — low precision (0.3333)
- `assessment` — low precision (0.3293); high df (167)
- `assets` — low precision (0.1875)
- `associated` — low precision (0.2456); high df (338)
- `association` — low precision (0.2449)
- `asynchronous` — low precision (0.25)
- `atomic` — low precision (0.2955)
- `attacks` — low precision (0.3125)
- `attention` — low precision (0.21)
- `autonomous` — low precision (0.2874)
- `available` — low precision (0.2663); high df (353)
- `awards` — low precision (0.2)
- `b` — low precision (0.254)
- `bandwidth` — low precision (0.3182)
- `basic` — low precision (0.2408); high df (191)
- `basis` — low precision (0.189); high df (164)
- `bayesian` — low precision (0.3214)
- `beamforming` — low precision (0.3333)
- `because` — low precision (0.2492); high df (313)
- `become` — low precision (0.2323); high df (198)
- `been` — low precision (0.2477); high df (654)
- `behavior` — low precision (0.2508); high df (311)
- `behavioral` — low precision (0.2738); high df (168)
- `benefit` — low precision (0.2769); high df (195)
- `best` — low precision (0.2532); high df (158)
- `better` — low precision (0.272); high df (364)
- `beyond` — low precision (0.2129); high df (202)
- `big` — low precision (0.3125)
- `binding` — low precision (0.3125)
- `binding sites` — low precision (0.2857)
- `bioinformatics` — low precision (0.3478)
- `biological` — high df (293)
- `biology` — high df (230)
- `biomedical` — low precision (0.3095)
- `black` — low precision (0.3043)
- `blood` — low precision (0.3205)
- `body` — low precision (0.2268)
- `bone marrow` — low precision (0.3333)
- `boston` — low precision (0.2409)
- `bottleneck` — low precision (0.2857)
- `brain` — low precision (0.2652); high df (181)
- `bridge` — low precision (0.2113)
- `bring` — low precision (0.2482)
- `broad` — low precision (0.2319); high df (276)
- `broadening` — low precision (0.2264)
- `broadening participation` — low precision (0.3333)
- `build` — low precision (0.251); high df (251)
- `building` — low precision (0.3195); high df (241)
- `burden` — low precision (0.2653)

... and 1176 more (see outputs/kw_vocab_candidates.json for the full list, filter on max_topic_precision/df_corpus).

— trust below this line —


## 4. Dropped-as-generic / small-cluster drop candidates

Nothing vanishes silently — every candidate for dropping is listed here with its reason and its terms, so you can override the auto-flag.

- Leaf 1 (3 terms): candidate for drop: cluster below 5-term floor, not yet reviewed
  - terms: should, radical, precisely
- Leaf 4 (2 terms): candidate for drop: cluster below 5-term floor, not yet reviewed
  - terms: interpretation, mine
- Leaf 5 (1 terms): candidate for drop: cluster below 5-term floor, not yet reviewed
  - terms: become
- Leaf 6 (3 terms): candidate for drop: cluster below 5-term floor, not yet reviewed
  - terms: growing, favor, yielding
- Leaf 8 (3 terms): candidate for drop: cluster below 5-term floor, not yet reviewed
  - terms: proximity, minutes, matching
- Leaf 9 (1 terms): candidate for drop: cluster below 5-term floor, not yet reviewed
  - terms: ve
- Leaf 18 (2 terms): candidate for drop: cluster below 5-term floor, not yet reviewed
  - terms: higher, ap
- Leaf 22 (2 terms): candidate for drop: cluster below 5-term floor, not yet reviewed
  - terms: alternative, cas
- Leaf 24 (2 terms): candidate for drop: cluster below 5-term floor, not yet reviewed
  - terms: disruption, timing
- Leaf 25 (1 terms): candidate for drop: cluster below 5-term floor, not yet reviewed
  - terms: tracing

## 5. Leaf keyword lists

### Leaf 1 — should, radical, precisely  (parent: P1)
- keywords: should, radical, precisely
- ⚠ AUTO-FLAG: only 3 term(s) in this cluster — likely PI-idiolect noise rather than a real theme. Verify before accepting; consider moving to dropped_leaves instead.

### Leaf 2 — neurons, neuronal, neural circuits  (parent: P1)
- keywords: neurons, neuronal, neural circuits, nervous system, synaptic, individual neurons, image, reconstruction, optogenetic, acquired, synapses, dendritic, worm, c elegans, mr

### Leaf 3 — biochemical, molecular, cellular  (parent: P1)
- keywords: biochemical, molecular, cellular, therapeutic, in vivo, proteins, in vitro, signaling, cell, binding, expression, diseases, acid, molecules, inhibition

### Leaf 4 — interpretation, mine  (parent: P2)
- keywords: interpretation, mine
- ⚠ AUTO-FLAG: only 2 term(s) in this cluster — likely PI-idiolect noise rather than a real theme. Verify before accepting; consider moving to dropped_leaves instead.

### Leaf 5 — become  (parent: P2)
- keywords: become
- ⚠ AUTO-FLAG: only 1 term(s) in this cluster — likely PI-idiolect noise rather than a real theme. Verify before accepting; consider moving to dropped_leaves instead.

### Leaf 6 — growing, favor, yielding  (parent: P2)
- keywords: growing, favor, yielding
- ⚠ AUTO-FLAG: only 3 term(s) in this cluster — likely PI-idiolect noise rather than a real theme. Verify before accepting; consider moving to dropped_leaves instead.

### Leaf 7 — evidence, age, findings  (parent: P2)
- keywords: evidence, age, findings, population, behavioral, adults, interventions, whether, examine, mental, differences, longitudinal, life, factors, older

### Leaf 8 — proximity, minutes, matching  (parent: P2)
- keywords: proximity, minutes, matching
- ⚠ AUTO-FLAG: only 3 term(s) in this cluster — likely PI-idiolect noise rather than a real theme. Verify before accepting; consider moving to dropped_leaves instead.

### Leaf 9 — ve  (parent: P2)
- keywords: ve
- ⚠ AUTO-FLAG: only 1 term(s) in this cluster — likely PI-idiolect noise rather than a real theme. Verify before accepting; consider moving to dropped_leaves instead.

### Leaf 10 — environment, cross-disciplinary, flame  (parent: P3)
- keywords: environment, cross-disciplinary, flame, multidisciplinary, fire, pd

### Leaf 11 — coastal, sediment, coast  (parent: P3)
- keywords: coastal, sediment, coast, ecology, river, environmental, ecological, nutrient, ecosystem services, wetlands, climate change, climate, land, tide, sea

### Leaf 12 — attend, student travel, travel  (parent: P4)
- keywords: attend, student travel, travel, students to attend, acm, attending, present their work, travel support, provides travel, travel funds, opportunity to present, leading-edge research, student travel grant, venue, conference

### Leaf 13 — economic, build, organizations  (parent: P4)
- keywords: economic, build, organizations, issues, stakeholders, best, policy, social, social science, urban, building, society, researchers, needs, government

### Leaf 14 — faculty, professional development, professional  (parent: P4)
- keywords: faculty, professional development, professional, leadership, institutions, urm, recruitment, academic, members, diverse, mentor, partnership, career, environmental health, college

### Leaf 15 — steel, earthquake, collapse  (parent: P5)
- keywords: steel, earthquake, collapse, earthquake engineering, performance-based, existing structures, full-scale, neesr, seismic, structural systems, nees, wind, civil, earthquake hazards, natural hazards

### Leaf 16 — materials, temperature, optical  (parent: P5)
- keywords: materials, temperature, optical, thermal, films, nanostructures, thin, fundamental, fabrication, high school, semiconductor, nanoscale, highly, outreach, surface

### Leaf 17 — string theory, representation theory, algebraic  (parent: P6)
- keywords: string theory, representation theory, algebraic, symmetry, areas of mathematics, algebras, quantum groups, integrable systems, invariants, algebraic geometry, combinatorics, mathematicians, manifolds, elliptic, cluster algebras

### Leaf 18 — higher, ap  (parent: P7)
- keywords: higher, ap
- ⚠ AUTO-FLAG: only 2 term(s) in this cluster — likely PI-idiolect noise rather than a real theme. Verify before accepting; consider moving to dropped_leaves instead.

### Leaf 19 — robust, framework, tasks  (parent: P8)
- keywords: robust, framework, tasks, cyber-physical systems, cyber-physical, vision, systems theory, reinforcement learning, uncertainty, inference, bayesian, algorithms, computationally efficient, probabilistic, control systems

### Leaf 20 — software, code, project develops  (parent: P8)
- keywords: software, code, project develops, cloud, open-source, secure, scalable, security, computer systems, developers, develops, significance and importance, twc, open-source software, attacks

### Leaf 21 — testbed, wireless, deployment  (parent: P8)
- keywords: testbed, wireless, deployment, radio, rf, software-defined, cross-layer, sensor networks, receiver, interference, operating, power, stack, data rates, power consumption

### Leaf 22 — alternative, cas  (parent: P8)
- keywords: alternative, cas
- ⚠ AUTO-FLAG: only 2 term(s) in this cluster — likely PI-idiolect noise rather than a real theme. Verify before accepting; consider moving to dropped_leaves instead.

### Leaf 23 — detect, detection, detecting  (parent: P8)
- keywords: detect, detection, detecting, monitor, accurate, accuracy, sensor technology, false, safety, severe, extraction, against, identification, comprehensive, simultaneous

### Leaf 24 — disruption, timing  (parent: P9)
- keywords: disruption, timing
- ⚠ AUTO-FLAG: only 2 term(s) in this cluster — likely PI-idiolect noise rather than a real theme. Verify before accepting; consider moving to dropped_leaves instead.

### Leaf 25 — tracing  (parent: P9)
- keywords: tracing
- ⚠ AUTO-FLAG: only 1 term(s) in this cluster — likely PI-idiolect noise rather than a real theme. Verify before accepting; consider moving to dropped_leaves instead.


## 6. k-sweep (silhouette by k)

| k | silhouette |
|---|---|
| 6 | 0.1254 |
| 7 | 0.122 |
| 8 | 0.1152 |
| 9 | 0.1418 ← chosen k_parent |
| 10 | 0.1344 |
| 11 | 0.1314 |
| 12 | 0.1217 |
| 13 | 0.1323 |
| 14 | 0.1216 |
| 15 | 0.1209 |
| 16 | 0.1134 |
| 25 | 0.1241 ← chosen k_leaf |
| 26 | 0.118 |
| 27 | 0.1162 |
| 28 | 0.1137 |
| 29 | 0.1102 |
| 30 | 0.114 |
| 31 | 0.1092 |
| 32 | 0.1058 |
| 33 | 0.1015 |
| 34 | 0.0984 |
| 35 | 0.0975 |
| 36 | 0.0971 |
| 37 | 0.0955 |
| 38 | 0.0971 |
| 39 | 0.0966 |
| 40 | 0.0956 |
| 41 | 0.0942 |
| 42 | 0.0928 |
| 43 | 0.0926 |
| 44 | 0.0949 |
| 45 | 0.0974 |
| 46 | 0.095 |
| 47 | 0.0946 |
| 48 | 0.0947 |
| 49 | 0.0922 |
| 50 | 0.0908 |

## 7. Downstream files to edit if the parent count changes

If curation changes the accepted parent count away from 8, these need manual sync
(per docs/TOPIC_MODEL_REFIT_CHECKLIST.md's existing checklist for this):
- `src/build_viz_aggregates.py` — `PARENT_NAMES` / `PARENT_COLORS`
- `docs/TopicVizPrototypes/shared/enrico.js` — `PARENT_COLORS`, `parentName()`/`parentColor()`
- `docs/TopicVizPrototypes/what_we_can_see/constants.js` — `TP_COLORS` (parent-indexed)
- `CLAUDE.md`'s "Topic modeling — state of play" section (parent count is stated there)


## 8. The 20 largest currently-Unassigned grants by dollars (of 725 total, giving the $ headline faces)

| grant_id | title | dollars |
|---|---|---|
| 714230 | PUERTO RICO TESTSITE FOR EXPLORING CONTAMINATION THREATS (PROTECT) | $38,591,094 |
| 672764 | CELEST: A Center of Excellence for Learning in Education, Science, and Technolog | $19,399,383 |
| 1356036 | Environmental Influences on Child Health Outcomes in Puerto Rico (ECHO-PRO) | $19,147,769 |
| 1594618 | Mid-scale RI-1 (M1:IP): Observatory for Online Human and Platform Behavior | $16,217,700 |
| 1196051 | Environmental Influences on Child Health Outcomes in Puerto Rico (ECHO-PRO) | $12,957,363 |
| 78396 | Grant | $6,750,000 |
| 989777 | The Integrative Genomics of Acute Asthma Control | $6,509,743 |
| 1720106 | A prototype flight for the GRAMS project | $6,300,000 |
| 1090545 | Administrative Core | $6,021,042 |
| 1149950 | GuMI: New In Vitro Platforms to Parse the Human Gut Epithelial-Microbiome-Immune | $5,216,560 |
| 823471 | Multi-Disciplinary Preparation of Next Generation Information Assurance Practiti | $4,962,084 |
| 1723358 | CyberCorps Scholarship for Service (Renewal): Securing the Future: Scholarship f | $4,874,905 |
| 931992 | Systems Approach to Unraveling the Genetic Basis of Heart Failure | $4,741,214 |
| 1280898 | Renewal: SFS @ Northeastern - a multi-disciplinary approach | $4,600,000 |
| 1280909 | NSF-SFS: Arizona Cyber Defense Scholarship | $3,997,784 |
| 1051628 | Center for Research on Early Childhood Exposure and Development in Puerto Rico ( | $3,625,488 |
| 1374512 | Orally Bioavailable 4(1H)-Quinolones with Multi-Stage Antimalarial Activity | $3,553,386 |
| 1270145 | A Continuous Manufacturing Platform for Complex Dosage Forms | $3,515,319 |
| 1786469 | SCC-LSR: From Technology to Humans: Protecting Users of Neural and Medical Impla | $3,500,000 |
| 970483 | Hit-to-lead discovery for sleeping sickness via industry-academic partnership | $3,376,103 |