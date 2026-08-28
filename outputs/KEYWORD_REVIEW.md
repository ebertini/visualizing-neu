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

- Full harvested vocabulary: **35640 terms**, of which
  **29 grants** have zero matching
  candidate terms at all (the irreducible floor — genuinely text-less docs).
- Pruned to **2509 terms** (2500 by rank +
  9 backfilled): **29 grants**
  still match zero terms — equal to the floor above, by construction (verified by
  an assert in kw_vocab_discover.py).
- Parent clustering: k=8
  (silhouette=0.1796); leaf clustering:
  k=33 (silhouette=0.1345).
- Nesting check: **0 leaf clusters
  span more than one parent** (should be 0 — Plan B guarantees this by construction).
- ARI (doc-centroid grouping vs. full c-TF-IDF-loading grouping):
  **0.1762** — low means the semantic
  grouping is adding real information beyond simple topic co-occurrence, which is
  what you want to see.


## 2. Candidate parent groups

### P1 — 759 terms (30.3%)
- Top terms: molecular, biochemical, the molecular, proteins, cellular, signaling, therapeutic, binding, in vivo, cell, we have, in vitro
- Contributing legacy topics: topic 22 (concentration=38.971, n=1364), topic 11 (concentration=21.552, n=1250), topic 23 (concentration=15.125, n=484)

### P2 — 571 terms (22.8%)
- Top terms: hardware, solutions, deployment, reliable, security, and software, architecture, hardware and, and security, scenarios, performance, operating
- Contributing legacy topics: topic 7 (concentration=15.552, n=1353), topic 15 (concentration=9.68, n=484), topic 19 (concentration=9.463, n=388)

### P5 — 440 terms (17.5%)
- Top terms: interventions, adults, behavioral, findings, outcomes, population, mental, cognitive, longitudinal, and cognitive, people, children
- Contributing legacy topics: topic 1 (concentration=13.866, n=1858), topic 6 (concentration=13.056, n=1162), topic 29 (concentration=8.864, n=195)

### P8 — 286 terms (11.4%)
- Top terms: attend, to present, nsf, conference the, student, to attend, conference in, their work, researchers and, conference, present their, students to
- Contributing legacy topics: topic 26 (concentration=33.345, n=967), topic 10 (concentration=9.608, n=711), topic 0 (concentration=6.74, n=1813)

### P3 — 211 terms (8.4%)
- Top terms: physics, physics and, symmetry, quantum, geometry, finite, geometry and, areas of, string theory, the physics, dimensional, mathematics
- Contributing legacy topics: topic 2 (concentration=17.574, n=2267), topic 0 (concentration=8.695, n=2339), topic 12 (concentration=1.31, n=76)

### P7 — 201 terms (8.0%)
- Top terms: environmental, coastal, and environmental, water, river, environmental science, of coastal, sediment, land, climate, flooding, flood
- Contributing legacy topics: topic 4 (concentration=10.786, n=1111), topic 13 (concentration=7.765, n=396), topic 16 (concentration=5.896, n=283)

### P4 — 40 terms (1.6%)
- Top terms: analysis, data analysis, information, datasets, data in, of data, collection, statistical, mining, methods, data mining, databases
- Contributing legacy topics: topic 9 (concentration=1.747, n=145), topic 20 (concentration=0.811, n=30), topic 0 (concentration=0.766, n=206)

### P6 — 1 terms (0.0%)
- Top terms: yielding
- Contributing legacy topics: topic 0 (concentration=0.015, n=4)


## 3. Flagged terms needing disambiguation (1391/2509 = 55.4%) — the most valuable page

— review these; everything else can be skimmed —

- `12` — low precision (0.3333)
- `12 months` — low precision (0.2857)
- `2012` — low precision (0.2353)
- `2013` — low precision (0.2)
- `2014` — low precision (0.2143)
- `2016` — low precision (0.2353)
- `2019` — low precision (0.1818)
- `2020` — low precision (0.3103)
- `2023` — low precision (0.2308)
- `2d` — low precision (0.3478)
- `3` — low precision (0.2566); high df (678)
- `3-d` — low precision (0.2667)
- `3d` — low precision (0.2184)
- `4` — low precision (0.2297); high df (283)
- `6` — low precision (0.2526)
- `a center` — low precision (0.2766)
- `a comprehensive` — low precision (0.2632)
- `a low` — low precision (0.3333)
- `a new` — low precision (0.2568); high df (440)
- `a novel` — low precision (0.2691); high df (249)
- `ability` — low precision (0.3198); high df (369)
- `about` — low precision (0.2729); high df (469)
- `about the` — low precision (0.2591); high df (193)
- `abroad` — low precision (0.25)
- `academia` — low precision (0.2698)
- `academic` — low precision (0.2532); high df (154)
- `access` — low precision (0.314); high df (242)
- `accurate` — low precision (0.3235)
- `acid` — low precision (0.2955)
- `acting` — low precision (0.25)
- `action` — low precision (0.1667)
- `activation` — low precision (0.2394)
- `activation of` — low precision (0.2963)
- `active` — low precision (0.2564); high df (195)
- `activities` — low precision (0.2035); high df (462)
- `activity and` — low precision (0.2059)
- `activity of` — low precision (0.2093)
- `acute` — low precision (0.3235)
- `adaptive` — low precision (0.2333)
- `address` — low precision (0.2961); high df (466)
- `adjusted` — low precision (0.25)
- `administration` — low precision (0.3158)
- `adults` — low precision (0.3444)
- `advance` — low precision (0.2626); high df (297)
- `advanced` — low precision (0.2977); high df (309)
- `advances in the` — low precision (0.2667)
- `advisory` — low precision (0.3261)
- `affect` — low precision (0.2313); high df (160)
- `after` — low precision (0.2437); high df (197)
- `against` — low precision (0.2763); high df (152)
- `age` — low precision (0.24)
- `agencies` — low precision (0.2951)
- `agents` — low precision (0.2759)
- `aging` — low precision (0.2727)
- `aim 1` — low precision (0.1986)
- `aim 1 we` — low precision (0.2)
- `aim 2` — low precision (0.2014)
- `aim 2 we` — low precision (0.1935)
- `aim 3` — low precision (0.1731)
- `aims to` — low precision (0.2508); high df (299)
- `algorithms` — low precision (0.3115); high df (305)
- `algorithmic` — low precision (0.3043)
- `all` — low precision (0.2496); high df (581)
- `alliance` — low precision (0.3125)
- `allocation` — low precision (0.2353)
- `allow` — low precision (0.3037); high df (349)
- `along` — low precision (0.2216); high df (167)
- `alternative` — low precision (0.2952)
- `an ecosystem` — low precision (0.25)
- `an opportunity` — low precision (0.2075)
- `an opportunity to` — low precision (0.3333)
- `analyses` — low precision (0.2524)
- `analysis` — low precision (0.2837); high df (557)
- `analysis and` — low precision (0.2231)
- `analysis of` — low precision (0.2828); high df (198)
- `analysis of the` — low precision (0.1944)
- `analytical` — low precision (0.2386)
- `and a` — low precision (0.2347); high df (311)
- `and active` — low precision (0.2353)
- `and behavior` — low precision (0.2258)
- `and cellular` — low precision (0.3393)
- `and conference` — low precision (0.3)
- `and control` — low precision (0.2991)
- `and design` — low precision (0.2162)
- `and design of` — low precision (0.2273)
- `and engineering` — low precision (0.2471); high df (170)
- `and environmental` — low precision (0.2289)
- `and human` — low precision (0.2)
- `and in` — low precision (0.229); high df (262)
- `and learning` — low precision (0.2857)
- `and maintenance` — low precision (0.3077)
- `and social` — low precision (0.2178)
- `and software` — low precision (0.2533)
- `and systems` — low precision (0.3171)
- `and the associated` — low precision (0.3077)
- `and their` — low precision (0.2218); high df (257)
- `and thus` — low precision (0.1346)
- `and training` — low precision (0.2524)
- `and trust` — low precision (0.3333)
- `and will` — low precision (0.1839); high df (261)
- `animal` — low precision (0.1954)
- `annotations` — low precision (0.3333)
- `another` — low precision (0.2128)
- `any` — low precision (0.2793); high df (179)
- `applicant` — low precision (0.2099); high df (262)
- `applications are` — low precision (0.2778)
- `application we` — low precision (0.25)
- `approach to` — low precision (0.2804); high df (189)
- `approaches` — low precision (0.2466); high df (446)
- `approximately` — low precision (0.2692)
- `architecture` — low precision (0.3273)
- `areas of` — low precision (0.2222)
- `arise` — low precision (0.1957)
- `array` — low precision (0.2588)
- `articles` — low precision (0.2963)
- `arts` — low precision (0.1538)
- `as a` — low precision (0.2619); high df (611)
- `as the` — low precision (0.2545); high df (385)
- `as well as` — low precision (0.2709); high df (598)
- `assessment` — low precision (0.3293); high df (167)
- `assessment of` — low precision (0.3049)
- `assets` — low precision (0.1875)
- `associated` — low precision (0.2456); high df (338)
- `associated with` — low precision (0.2299); high df (261)
- `asynchronous` — low precision (0.25)
- `at scale` — low precision (0.3333)
- `at the` — low precision (0.221); high df (620)
- `at the time` — low precision (0.2727)
- `attacks` — low precision (0.3125)
- `attacks the` — low precision (0.3333)
- `attention` — low precision (0.21)
- `autonomous` — low precision (0.2874)
- `available` — low precision (0.2663); high df (353)
- `available to` — low precision (0.2024)
- `awards` — low precision (0.2)
- `b` — low precision (0.254)
- `bandwidth` — low precision (0.3182)
- `based on` — low precision (0.2484); high df (471)
- `basis` — low precision (0.189); high df (164)
- `basis of` — low precision (0.2239)
- `be a` — low precision (0.2727)
- `be held` — low precision (0.1972)
- `be used` — low precision (0.2593); high df (428)
- `be used to` — low precision (0.2587); high df (286)
- `beamforming` — low precision (0.3333)
- `because` — low precision (0.2492); high df (313)
- `become` — low precision (0.2323); high df (198)
- `been` — low precision (0.2477); high df (654)
- `behavior` — low precision (0.2508); high df (311)
- `behavior of` — low precision (0.2716)

... and 1241 more (see outputs/kw_vocab_candidates.json for the full list, filter on max_topic_precision/df_corpus).

— trust below this line —


## 4. Dropped-as-generic / small-cluster drop candidates

Nothing vanishes silently — every candidate for dropping is listed here with its reason and its terms, so you can override the auto-flag.

- Leaf 1 (2 terms): candidate for drop: cluster below 5-term floor, not yet reviewed
  - terms: burden on, should
- Leaf 9 (2 terms): candidate for drop: cluster below 5-term floor, not yet reviewed
  - terms: of coupled, scale in
- Leaf 14 (2 terms): candidate for drop: cluster below 5-term floor, not yet reviewed
  - terms: anomalous, in such
- Leaf 15 (1 terms): candidate for drop: cluster below 5-term floor, not yet reviewed
  - terms: tracing
- Leaf 22 (1 terms): candidate for drop: cluster below 5-term floor, not yet reviewed
  - terms: from low
- Leaf 23 (2 terms): candidate for drop: cluster below 5-term floor, not yet reviewed
  - terms: alternative, cas
- Leaf 25 (1 terms): candidate for drop: cluster below 5-term floor, not yet reviewed
  - terms: yielding
- Leaf 27 (3 terms): candidate for drop: cluster below 5-term floor, not yet reviewed
  - terms: fire, flame, pd
- Leaf 29 (1 terms): candidate for drop: cluster below 5-term floor, not yet reviewed
  - terms: and active
- Leaf 32 (2 terms): candidate for drop: cluster below 5-term floor, not yet reviewed
  - terms: proximity, minutes

## 5. Leaf keyword lists

### Leaf 1 — burden on, should  (parent: P1)
- keywords: burden on, should
- ⚠ AUTO-FLAG: only 2 term(s) in this cluster — likely PI-idiolect noise rather than a real theme. Verify before accepting; consider moving to dropped_leaves instead.

### Leaf 2 — the time of, tolerance to, time of  (parent: P1)
- keywords: the time of, tolerance to, time of, selection of, type 1, at the time, tolerance, governing the, the parameters, selection, the time

### Leaf 3 — microscopy, imaging, resolution  (parent: P1)
- keywords: microscopy, imaging, resolution, fluorescence, 3d, experimental, mechanical, the mechanical, optical, would, force, response of, spatial, light, high-resolution

### Leaf 4 — biochemical, molecular, the molecular  (parent: P1)
- keywords: biochemical, molecular, the molecular, proteins, binding, we have, therapeutic, signaling, cellular, in vivo, acid, in vitro, cell, provided by, molecules

### Leaf 5 — project is to, detect, of this project  (parent: P2)
- keywords: project is to, detect, of this project, can be, develop a, detection, techniques, detecting, based on, to develop a, this project is, project is, identification and, the goal of, to develop

### Leaf 6 — vulnerability, resilience, subject to  (parent: P2)
- keywords: vulnerability, resilience, subject to, the vulnerability, timing, disruption

### Leaf 7 — software, code, security  (parent: P2)
- keywords: software, code, security, project s, secure, developers, project develops, cloud, systems are, computer systems, scalable, the security, attacks, the project s, to make

### Leaf 8 — deployment, wireless, testbed  (parent: P2)
- keywords: deployment, wireless, testbed, operating, power, performance, deployment of, radio, sensor networks, rf, cross-layer, of wireless, real-time, hardware, solutions

### Leaf 9 — of coupled, scale in  (parent: P3)
- keywords: of coupled, scale in
- ⚠ AUTO-FLAG: only 2 term(s) in this cluster — likely PI-idiolect noise rather than a real theme. Verify before accepting; consider moving to dropped_leaves instead.

### Leaf 10 — materials, fundamental, materials and  (parent: P3)
- keywords: materials, fundamental, materials and, thin, films, spin, thermal, temperature, the fundamental, electronic, outreach, high school, physics of, the physics of, properties

### Leaf 11 — related, related to, continue to  (parent: P3)
- keywords: related, related to, continue to, continue, groups, will continue to, series, and their, theme, years

### Leaf 12 — the lhc, new physics, the standard model  (parent: P3)
- keywords: the lhc, new physics, the standard model, lhc, of particle physics, collider, hadron, beyond the standard, the higgs, higgs, particle physics, the standard, of particle, boson, the cms

### Leaf 13 — algebraic, invariants, of mathematics  (parent: P3)
- keywords: algebraic, invariants, of mathematics, representation theory, combinatorics, theory of, the theory, lie, algebras, manifolds, quantum groups, theory and, symmetries of, geometric, integrable systems

### Leaf 14 — anomalous, in such  (parent: P3)
- keywords: anomalous, in such
- ⚠ AUTO-FLAG: only 2 term(s) in this cluster — likely PI-idiolect noise rather than a real theme. Verify before accepting; consider moving to dropped_leaves instead.

### Leaf 15 — tracing  (parent: P3)
- keywords: tracing
- ⚠ AUTO-FLAG: only 1 term(s) in this cluster — likely PI-idiolect noise rather than a real theme. Verify before accepting; consider moving to dropped_leaves instead.

### Leaf 16 — infectious, influenza, pandemic  (parent: P4)
- keywords: infectious, influenza, pandemic, epidemic, shortages, infection, ve

### Leaf 17 — analysis, data analysis, datasets  (parent: P4)
- keywords: analysis, data analysis, datasets, information, data in, of data, statistical, methods, mining, data mining, collection, analysis and, databases, data science, sets

### Leaf 18 — robots, the robot, robotics  (parent: P5)
- keywords: robots, the robot, robotics, human-robot, manipulation, advance, movement, assistive, this research, control, of complex, locomotion, project will advance, behavior, will advance

### Leaf 19 — due to, lead to, a comprehensive  (parent: P5)
- keywords: due to, lead to, a comprehensive, optimal, research is, parameters, comprehensive, failure, underlying, progressive, limited, the present

### Leaf 20 — social, social and, and social  (parent: P5)
- keywords: social, social and, and social, about, attitudes, the social, work and, economic, world, qualitative, decisions, skills, about the, own, what

### Leaf 21 — age, evidence, adults  (parent: P5)
- keywords: age, evidence, adults, and cognitive, behavioral, whether, differences, examine, findings, interventions, aim 3, population, differences in, mental, life

### Leaf 22 — from low  (parent: P5)
- keywords: from low
- ⚠ AUTO-FLAG: only 1 term(s) in this cluster — likely PI-idiolect noise rather than a real theme. Verify before accepting; consider moving to dropped_leaves instead.

### Leaf 23 — alternative, cas  (parent: P5)
- keywords: alternative, cas
- ⚠ AUTO-FLAG: only 2 term(s) in this cluster — likely PI-idiolect noise rather than a real theme. Verify before accepting; consider moving to dropped_leaves instead.

### Leaf 24 — use of, potential, designed to  (parent: P5)
- keywords: use of, potential, designed to, evaluation, designed, evaluation of, testing, the use of, with a, the potential, successful, evaluation of the, neglect

### Leaf 25 — yielding  (parent: P6)
- keywords: yielding
- ⚠ AUTO-FLAG: only 1 term(s) in this cluster — likely PI-idiolect noise rather than a real theme. Verify before accepting; consider moving to dropped_leaves instead.

### Leaf 26 — steel, earthquake, full-scale  (parent: P7)
- keywords: steel, earthquake, full-scale, collapse, performance-based, of steel, existing structures, civil, of building, wind, seismic, civil engineering, the nees, structural systems, of structures

### Leaf 27 — fire, flame, pd  (parent: P7)
- keywords: fire, flame, pd
- ⚠ AUTO-FLAG: only 3 term(s) in this cluster — likely PI-idiolect noise rather than a real theme. Verify before accepting; consider moving to dropped_leaves instead.

### Leaf 28 — environmental, coastal, environmental science  (parent: P7)
- keywords: environmental, coastal, environmental science, and environmental, river, sediment, of coastal, water, land, ecology, climate, and water, of environmental, in environmental, climate change

### Leaf 29 — and active  (parent: P7)
- keywords: and active
- ⚠ AUTO-FLAG: only 1 term(s) in this cluster — likely PI-idiolect noise rather than a real theme. Verify before accepting; consider moving to dropped_leaves instead.

### Leaf 30 — nsf, student, opportunities  (parent: P8)
- keywords: nsf, student, opportunities, faculty, institutions, universities, professional, diverse, students to, college, science and, university of, academic, students who, national

### Leaf 31 — to attend, conference on, attend  (parent: P8)
- keywords: to attend, conference on, attend, student travel, to present their, travel, conference the, present their, the travel, international conference on, to present, students to attend, acm, travel support for, present their work

### Leaf 32 — proximity, minutes  (parent: P8)
- keywords: proximity, minutes
- ⚠ AUTO-FLAG: only 2 term(s) in this cluster — likely PI-idiolect noise rather than a real theme. Verify before accepting; consider moving to dropped_leaves instead.

### Leaf 33 — will have, that will, with an  (parent: P8)
- keywords: will have, that will, with an, and a, have the, environment, to a, than, of an, higher


## 6. k-sweep (silhouette by k)

| k | silhouette |
|---|---|
| 6 | 0.2046 |
| 7 | 0.1923 |
| 8 | 0.1796 ← chosen k_parent |
| 9 | 0.17 |
| 10 | 0.165 |
| 11 | 0.1547 |
| 12 | 0.144 |
| 13 | 0.1429 |
| 14 | 0.1329 |
| 15 | 0.1297 |
| 16 | 0.128 |
| 25 | 0.1145 |
| 26 | 0.1125 |
| 27 | 0.1106 |
| 28 | 0.1068 |
| 29 | 0.1029 |
| 30 | 0.1203 |
| 31 | 0.1182 |
| 32 | 0.1281 |
| 33 | 0.1345 ← chosen k_leaf |
| 34 | 0.133 |
| 35 | 0.1325 |
| 36 | 0.1334 |
| 37 | 0.1329 |
| 38 | 0.1221 |
| 39 | 0.1213 |
| 40 | 0.118 |
| 41 | 0.117 |
| 42 | 0.115 |
| 43 | 0.1142 |
| 44 | 0.1132 |
| 45 | 0.1129 |
| 46 | 0.1095 |
| 47 | 0.1174 |
| 48 | 0.1157 |
| 49 | 0.1151 |
| 50 | 0.1051 |

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