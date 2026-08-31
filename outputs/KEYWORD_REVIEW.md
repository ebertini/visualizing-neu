# Keyword-Topic Review Sheet (source: curated)


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

Sorted so terms sitting inside a large (>=50-term, likely-accepted) leaf come first — those are the ones actually worth your time.

— review these; everything else can be skimmed —

- `researchers` — low precision (0.25); high df (484) — in: leaf 12 (189 terms)
- `public` — low precision (0.2794); high df (451) — in: leaf 12 (189 terms)
- `materials` — high df (353) — in: leaf 17 (132 terms)
- `social` — low precision (0.2866); high df (321) — in: leaf 12 (189 terms)
- `diverse` — low precision (0.2437); high df (316) — in: leaf 13 (172 terms)
- `cell` — low precision (0.3137); high df (306) — in: leaf 1 (641 terms)
- `algorithms` — low precision (0.3115); high df (305) — in: leaf 21 (114 terms)
- `molecular` — low precision (0.3108); high df (296) — in: leaf 1 (641 terms)
- `software` — low precision (0.2576); high df (295) — in: leaf 22 (284 terms)
- `energy` — low precision (0.3034); high df (267) — in: leaf 17 (132 terms)
- `stem` — low precision (0.278); high df (223) — in: leaf 13 (172 terms)
- `management` — low precision (0.2627); high df (217) — in: leaf 12 (189 terms)
- `clinical` — low precision (0.2972); high df (212) — in: leaf 3 (300 terms)
- `career` — low precision (0.2); high df (205) — in: leaf 13 (172 terms)
- `society` — low precision (0.2871); high df (202) — in: leaf 12 (189 terms)
- `needs` — low precision (0.2714); high df (199) — in: leaf 12 (189 terms)
- `risk` — low precision (0.2475); high df (198) — in: leaf 3 (300 terms)
- `cellular` — low precision (0.2708); high df (192) — in: leaf 1 (641 terms)
- `imaging` — low precision (0.2593); high df (189) — in: leaf 1 (641 terms)
- `proteins` — high df (183) — in: leaf 1 (641 terms)
- `machine learning` — low precision (0.3022); high df (182) — in: leaf 21 (114 terms)
- `faculty` — low precision (0.2818); high df (181) — in: leaf 13 (172 terms)
- `institutions` — low precision (0.2222); high df (180) — in: leaf 13 (172 terms)
- `in vivo` — low precision (0.2848); high df (165) — in: leaf 1 (641 terms)
- `women` — low precision (0.2236); high df (161) — in: leaf 13 (172 terms)
- `patients` — low precision (0.2803); high df (157) — in: leaf 3 (300 terms)
- `therapeutic` — low precision (0.2697); high df (152) — in: leaf 1 (641 terms)
- `economic` — low precision (0.2533) — in: leaf 12 (189 terms)
- `optimization` — low precision (0.2808) — in: leaf 21 (114 terms)
- `public health` — low precision (0.2727) — in: leaf 3 (300 terms)
- `conference` — low precision (0.1929) — in: leaf 11 (93 terms)
- `diversity` — low precision (0.2571) — in: leaf 13 (172 terms)
- `in vitro` — low precision (0.2464) — in: leaf 1 (641 terms)
- `characterization` — low precision (0.2721) — in: leaf 1 (641 terms)
- `policy` — low precision (0.2713) — in: leaf 12 (189 terms)
- `biomedical` — low precision (0.3095) — in: leaf 1 (641 terms)
- `signaling` — low precision (0.2114) — in: leaf 1 (641 terms)
- `mentoring` — low precision (0.1653) — in: leaf 13 (172 terms)
- `exposure` — low precision (0.3478) — in: leaf 6 (129 terms)
- `networking` — low precision (0.2566) — in: leaf 23 (164 terms)
- `mobile` — low precision (0.2545) — in: leaf 23 (164 terms)
- `professional` — low precision (0.2545) — in: leaf 13 (172 terms)
- `minority` — low precision (0.1667) — in: leaf 13 (172 terms)
- `optical` — low precision (0.3178) — in: leaf 1 (641 terms)
- `college` — low precision (0.2857) — in: leaf 13 (172 terms)
- `sensitivity` — low precision (0.2745) — in: leaf 1 (641 terms)
- `resolution` — low precision (0.2772) — in: leaf 1 (641 terms)
- `expression` — low precision (0.2784) — in: leaf 1 (641 terms)
- `spectrum` — low precision (0.3158) — in: leaf 23 (164 terms)
- `stress` — low precision (0.2581) — in: leaf 3 (300 terms)
- `organizations` — low precision (0.2418) — in: leaf 12 (189 terms)
- `programming` — low precision (0.3034) — in: leaf 22 (284 terms)
- `stakeholders` — low precision (0.2874) — in: leaf 12 (189 terms)
- `code` — low precision (0.3452) — in: leaf 22 (284 terms)
- `formal` — low precision (0.3452) — in: leaf 22 (284 terms)
- `electrical` — low precision (0.3293) — in: leaf 17 (132 terms)
- `universities` — low precision (0.2222) — in: leaf 13 (172 terms)
- `partnership` — low precision (0.25) — in: leaf 13 (172 terms)
- `urban` — low precision (0.2877) — in: leaf 12 (189 terms)
- `open-source` — low precision (0.3056) — in: leaf 22 (284 terms)
- `uncertainty` — low precision (0.3194) — in: leaf 21 (114 terms)
- `chronic` — low precision (0.2676) — in: leaf 3 (300 terms)
- `connectivity` — low precision (0.2609) — in: leaf 23 (164 terms)
- `microscopy` — low precision (0.2754) — in: leaf 1 (641 terms)
- `contrast` — low precision (0.2353) — in: leaf 1 (641 terms)
- `inference` — low precision (0.2985) — in: leaf 21 (114 terms)
- `travel` — low precision (0.3433) — in: leaf 11 (93 terms)
- `channel` — low precision (0.303) — in: leaf 23 (164 terms)
- `research experiences` — low precision (0.2769) — in: leaf 13 (172 terms)
- `status` — low precision (0.2769) — in: leaf 3 (300 terms)
- `transmission` — low precision (0.2615) — in: leaf 23 (164 terms)
- `agencies` — low precision (0.2951) — in: leaf 12 (189 terms)
- `law` — low precision (0.2333) — in: leaf 12 (189 terms)
- `stem education` — low precision (0.3167) — in: leaf 13 (172 terms)
- `leadership` — low precision (0.2881) — in: leaf 13 (172 terms)
- `layer` — low precision (0.2281) — in: leaf 23 (164 terms)
- `differential` — low precision (0.2679) — in: leaf 18 (125 terms)
- `mobility` — low precision (0.2364) — in: leaf 23 (164 terms)
- `classification` — low precision (0.1481) — in: leaf 21 (114 terms)
- `professional development` — low precision (0.2778) — in: leaf 13 (172 terms)
- `recruitment` — low precision (0.2308) — in: leaf 13 (172 terms)
- `scholars` — low precision (0.25) — in: leaf 13 (172 terms)
- `female` — low precision (0.28) — in: leaf 13 (172 terms)
- `inhibition` — low precision (0.22) — in: leaf 1 (641 terms)
- `burden` — low precision (0.2653) — in: leaf 3 (300 terms)
- `deep learning` — low precision (0.3061) — in: leaf 21 (114 terms)
- `stochastic` — low precision (0.1875) — in: leaf 21 (114 terms)
- `errors` — low precision (0.2766) — in: leaf 22 (284 terms)
- `black` — low precision (0.3043) — in: leaf 13 (172 terms)
- `acid` — low precision (0.2955) — in: leaf 1 (641 terms)
- `bandwidth` — low precision (0.3182) — in: leaf 23 (164 terms)
- `death` — low precision (0.2727) — in: leaf 3 (300 terms)
- `nodes` — low precision (0.2273) — in: leaf 23 (164 terms)
- `neural networks` — low precision (0.3023) — in: leaf 21 (114 terms)
- `demonstration` — low precision (0.3095) — in: leaf 17 (132 terms)
- `doctoral` — low precision (0.2381) — in: leaf 13 (172 terms)
- `retention` — low precision (0.2857) — in: leaf 13 (172 terms)
- `networked` — low precision (0.25) — in: leaf 23 (164 terms)
- `mentor` — low precision (0.2821) — in: leaf 13 (172 terms)
- `trainees` — low precision (0.3077) — in: leaf 13 (172 terms)
- `experimentation` — low precision (0.2432) — in: leaf 23 (164 terms)
- `static` — low precision (0.3243) — in: leaf 22 (284 terms)
- `high-level` — low precision (0.3056) — in: leaf 22 (284 terms)
- `acute` — low precision (0.3235) — in: leaf 3 (300 terms)
- `allocation` — low precision (0.2353) — in: leaf 23 (164 terms)
- `social science` — low precision (0.2353) — in: leaf 12 (189 terms)
- `dynamical systems` — low precision (0.303) — in: leaf 21 (114 terms)
- `graduate education` — low precision (0.2727) — in: leaf 13 (172 terms)
- `gender` — low precision (0.2188) — in: leaf 13 (172 terms)
- `mobile devices` — low precision (0.3103) — in: leaf 23 (164 terms)
- `bayesian` — low precision (0.3214) — in: leaf 21 (114 terms)
- `iron` — low precision (0.3333) — in: leaf 1 (641 terms)
- `youth` — low precision (0.2963) — in: leaf 12 (189 terms)
- `absorption` — low precision (0.3077) — in: leaf 1 (641 terms)
- `labor` — low precision (0.3077) — in: leaf 12 (189 terms)
- `probabilistic` — low precision (0.2308) — in: leaf 21 (114 terms)
- `cns` — low precision (0.24) — in: leaf 23 (164 terms)
- `multi-scale` — low precision (0.28) — in: leaf 17 (132 terms)
- `restoration` — low precision (0.32) — in: leaf 6 (129 terms)
- `open-source software` — low precision (0.2609) — in: leaf 22 (284 terms)
- `abstraction` — low precision (0.3333) — in: leaf 22 (284 terms)
- `decentralized` — low precision (0.25) — in: leaf 21 (114 terms)
- `delay` — low precision (0.3) — in: leaf 23 (164 terms)
- `scheduling` — low precision (0.2105) — in: leaf 23 (164 terms)
- `drinking water` — low precision (0.3333) — in: leaf 6 (129 terms)
- `venue` — low precision (0.2941) — in: leaf 11 (93 terms)
- `control theory` — low precision (0.3125) — in: leaf 21 (114 terms)
- `software engineering` — low precision (0.3125) — in: leaf 22 (284 terms)
- `classify` — low precision (0.2857) — in: leaf 21 (114 terms)
- `run-time` — low precision (0.2857) — in: leaf 22 (284 terms)
- `asynchronous` — low precision (0.25) — in: leaf 21 (114 terms)
- `scatter` — low precision (0.3) — in: leaf 1 (641 terms)
- `distributed algorithms` — low precision (0.2222) — in: leaf 21 (114 terms)
- `disturbance` — low precision (0.3333) — in: leaf 6 (129 terms)
- `on-demand` — low precision (0.2222) — in: leaf 23 (164 terms)
- `gaming` — low precision (0.3333) — in: leaf 14 (44 terms), leaf 22 (284 terms)
- `3` — low precision (0.2566); high df (678) — in: (not in any accepted-length leaf)
- `methods` — low precision (0.3037); high df (675) — in: (not in any accepted-length leaf)
- `system` — low precision (0.2478); high df (674) — in: (not in any accepted-length leaf)
- `been` — low precision (0.2477); high df (654) — in: (not in any accepted-length leaf)
- `its` — low precision (0.235); high df (634) — in: (not in any accepted-length leaf)
- `they` — low precision (0.2308); high df (624) — in: (not in any accepted-length leaf)
- `model` — low precision (0.2599); high df (604) — in: (not in any accepted-length leaf)
- `impact` — low precision (0.2479); high df (601) — in: (not in any accepted-length leaf)
- `potential` — low precision (0.2764); high df (597) — in: (not in any accepted-length leaf)
- `all` — low precision (0.2496); high df (581) — in: (not in any accepted-length leaf)
- `but` — low precision (0.2531); high df (573) — in: (not in any accepted-length leaf)
- `information` — low precision (0.286); high df (570) — in: (not in any accepted-length leaf)
- `techniques` — low precision (0.2968); high df (566) — in: (not in any accepted-length leaf)
- `graduate` — low precision (0.2407); high df (565) — in: (not in any accepted-length leaf)
- `analysis` — low precision (0.2837); high df (557) — in: (not in any accepted-length leaf)
- `while` — low precision (0.2802); high df (546) — in: (not in any accepted-length leaf)
- `engineering` — low precision (0.2575); high df (536) — in: (not in any accepted-length leaf)
- `first` — low precision (0.2642); high df (530) — in: (not in any accepted-length leaf)
- `different` — low precision (0.3071); high df (521) — in: (not in any accepted-length leaf)
- `education` — low precision (0.2297); high df (518) — in: leaf 14 (44 terms)
- `training` — low precision (0.2816); high df (515) — in: (not in any accepted-length leaf)
- `technology` — low precision (0.2959); high df (507) — in: (not in any accepted-length leaf)
- `human` — low precision (0.3088); high df (502) — in: (not in any accepted-length leaf)
- `knowledge` — low precision (0.299); high df (495) — in: (not in any accepted-length leaf)
- `critical` — low precision (0.2714); high df (490) — in: (not in any accepted-length leaf)
- `over` — low precision (0.2737); high df (486) — in: (not in any accepted-length leaf)
- `most` — low precision (0.2547); high df (475) — in: (not in any accepted-length leaf)
- `time` — low precision (0.2637); high df (474) — in: (not in any accepted-length leaf)
- `future` — low precision (0.2558); high df (473) — in: (not in any accepted-length leaf)
- `undergraduate` — low precision (0.2648); high df (472) — in: (not in any accepted-length leaf)
- `about` — low precision (0.2729); high df (469) — in: (not in any accepted-length leaf)
- `tools` — low precision (0.3034); high df (468) — in: (not in any accepted-length leaf)
- `address` — low precision (0.2961); high df (466) — in: (not in any accepted-length leaf)
- `control` — low precision (0.2618); high df (466) — in: (not in any accepted-length leaf)
- `learning` — low precision (0.2731); high df (465) — in: (not in any accepted-length leaf)
- `activities` — low precision (0.2035); high df (462) — in: (not in any accepted-length leaf)
- `community` — low precision (0.2446); high df (462) — in: (not in any accepted-length leaf)
- `there` — low precision (0.269); high df (461) — in: (not in any accepted-length leaf)
- `enable` — low precision (0.2725); high df (455) — in: (not in any accepted-length leaf)
- `fundamental` — low precision (0.2362); high df (453) — in: (not in any accepted-length leaf)
- `key` — low precision (0.2606); high df (449) — in: (not in any accepted-length leaf)
- `field` — low precision (0.1745); high df (447) — in: (not in any accepted-length leaf)
- `approaches` — low precision (0.2466); high df (446) — in: (not in any accepted-length leaf)
- `during` — low precision (0.2287); high df (446) — in: (not in any accepted-length leaf)
- `health` — low precision (0.2912); high df (443) — in: (not in any accepted-length leaf)
- `groups` — low precision (0.1946); high df (442) — in: (not in any accepted-length leaf)
- `complex` — low precision (0.3); high df (430) — in: (not in any accepted-length leaf)
- `scientific` — low precision (0.2518); high df (421) — in: (not in any accepted-length leaf)
- `multiple` — low precision (0.2749); high df (411) — in: (not in any accepted-length leaf)
- `mechanisms` — low precision (0.2983); high df (409) — in: (not in any accepted-length leaf)
- `focus` — low precision (0.2875); high df (407) — in: (not in any accepted-length leaf)
- `each` — low precision (0.2412); high df (398) — in: (not in any accepted-length leaf)
- `help` — low precision (0.2764); high df (398) — in: (not in any accepted-length leaf)
- `small` — low precision (0.2437); high df (398) — in: (not in any accepted-length leaf)
- `addition` — low precision (0.2594); high df (397) — in: (not in any accepted-length leaf)
- `performance` — low precision (0.2652); high df (396) — in: (not in any accepted-length leaf)
- `them` — low precision (0.2366); high df (393) — in: (not in any accepted-length leaf)
- `understand` — low precision (0.2474); high df (392) — in: (not in any accepted-length leaf)
- `team` — low precision (0.3274); high df (391) — in: (not in any accepted-length leaf)
- `properties` — low precision (0.2332); high df (386) — in: (not in any accepted-length leaf)
- `interactions` — low precision (0.2422); high df (384) — in: (not in any accepted-length leaf)
- `lead` — low precision (0.2801); high df (382) — in: (not in any accepted-length leaf)
- `processes` — low precision (0.2801); high df (382) — in: (not in any accepted-length leaf)
- `identify` — low precision (0.3018); high df (381) — in: (not in any accepted-length leaf)
- `range` — low precision (0.2152); high df (381) — in: (not in any accepted-length leaf)
- `structure` — low precision (0.2053); high df (380) — in: (not in any accepted-length leaf)
- `where` — low precision (0.2658); high df (380) — in: (not in any accepted-length leaf)
- `several` — low precision (0.277); high df (379) — in: (not in any accepted-length leaf)
- `than` — low precision (0.2533); high df (379) — in: (not in any accepted-length leaf)
- `when` — low precision (0.3005); high df (376) — in: (not in any accepted-length leaf)
- `role` — low precision (0.2347); high df (375) — in: (not in any accepted-length leaf)
- `existing` — low precision (0.3048); high df (374) — in: (not in any accepted-length leaf)
- `networks` — low precision (0.2554); high df (372) — in: (not in any accepted-length leaf)
- `ability` — low precision (0.3198); high df (369) — in: (not in any accepted-length leaf)
- `test` — low precision (0.2343); high df (367) — in: (not in any accepted-length leaf)
- `better` — low precision (0.272); high df (364) — in: (not in any accepted-length leaf)
- `computational` — low precision (0.2755); high df (363) — in: (not in any accepted-length leaf)
- `modeling` — low precision (0.2773); high df (357) — in: (not in any accepted-length leaf)
- `experimental` — low precision (0.2203); high df (354) — in: (not in any accepted-length leaf)
- `only` — low precision (0.2768); high df (354) — in: (not in any accepted-length leaf)
- `available` — low precision (0.2663); high df (353) — in: (not in any accepted-length leaf)
- `integrated` — low precision (0.2557); high df (352) — in: (not in any accepted-length leaf)
- `allow` — low precision (0.3037); high df (349) — in: (not in any accepted-length leaf)
- `environment` — low precision (0.2219); high df (347) — in: (not in any accepted-length leaf)
- `major` — low precision (0.2457); high df (346) — in: (not in any accepted-length leaf)
- `educational` — low precision (0.2362); high df (343) — in: (not in any accepted-length leaf)
- `make` — low precision (0.2449); high df (343) — in: (not in any accepted-length leaf)
- `who` — low precision (0.2799); high df (343) — in: (not in any accepted-length leaf)
- `effective` — low precision (0.2398); high df (342) — in: (not in any accepted-length leaf)
- `under` — low precision (0.2047); high df (342) — in: (not in any accepted-length leaf)
- `challenges` — low precision (0.2941); high df (340) — in: (not in any accepted-length leaf)
- `collaborative` — low precision (0.2861); high df (339) — in: (not in any accepted-length leaf)
- `associated` — low precision (0.2456); high df (338) — in: (not in any accepted-length leaf)
- `those` — low precision (0.2463); high df (337) — in: (not in any accepted-length leaf)
- `create` — low precision (0.3125); high df (336) — in: (not in any accepted-length leaf)
- `theory` — low precision (0.2388); high df (335) — in: (not in any accepted-length leaf)
- `number` — low precision (0.2922); high df (332) — in: (not in any accepted-length leaf)
- `function` — low precision (0.2591); high df (328) — in: (not in any accepted-length leaf)
- `unique` — low precision (0.2431); high df (325) — in: (not in any accepted-length leaf)
- `problems` — low precision (0.2601); high df (323) — in: (not in any accepted-length leaf)
- `outreach` — low precision (0.243); high df (321) — in: (not in any accepted-length leaf)
- `investigate` — low precision (0.2351); high df (319) — in: (not in any accepted-length leaf)
- `framework` — low precision (0.273); high df (315) — in: (not in any accepted-length leaf)
- `outcomes` — low precision (0.2571); high df (315) — in: (not in any accepted-length leaf)
- `recent` — low precision (0.2166); high df (314) — in: (not in any accepted-length leaf)
- `because` — low precision (0.2492); high df (313) — in: (not in any accepted-length leaf)
- `experiments` — low precision (0.2276); high df (312) — in: (not in any accepted-length leaf)
- `behavior` — low precision (0.2508); high df (311) — in: leaf 5 (17 terms)
- `communication` — low precision (0.2476); high df (311) — in: (not in any accepted-length leaf)
- `advanced` — low precision (0.2977); high df (309) — in: (not in any accepted-length leaf)
- `physical` — low precision (0.2215); high df (307) — in: (not in any accepted-length leaf)
- `could` — low precision (0.2353); high df (306) — in: (not in any accepted-length leaf)
- `national` — low precision (0.2451); high df (306) — in: (not in any accepted-length leaf)
- `state` — low precision (0.2778); high df (306) — in: (not in any accepted-length leaf)
- `computer` — low precision (0.2796); high df (304) — in: (not in any accepted-length leaf)
- `designed` — low precision (0.2633); high df (300) — in: (not in any accepted-length leaf)
- `experience` — low precision (0.2542); high df (299) — in: (not in any accepted-length leaf)
- `school` — low precision (0.2642); high df (299) — in: (not in any accepted-length leaf)
- `determine` — low precision (0.2416); high df (298) — in: (not in any accepted-length leaf)
- `scientists` — low precision (0.2987); high df (298) — in: (not in any accepted-length leaf)
- `advance` — low precision (0.2626); high df (297) — in: (not in any accepted-length leaf)
- `related` — low precision (0.2399); high df (296) — in: (not in any accepted-length leaf)
- `various` — low precision (0.2441); high df (295) — in: (not in any accepted-length leaf)
- `biological` — high df (293) — in: (not in any accepted-length leaf)
- `changes` — low precision (0.2655); high df (290) — in: (not in any accepted-length leaf)
- `devices` — low precision (0.3); high df (290) — in: (not in any accepted-length leaf)
- `graduate students` — low precision (0.2241); high df (290) — in: leaf 14 (44 terms)
- `interdisciplinary` — low precision (0.3056); high df (288) — in: (not in any accepted-length leaf)
- `opportunities` — low precision (0.2292); high df (288) — in: (not in any accepted-length leaf)
- `successful` — low precision (0.2021); high df (287) — in: (not in any accepted-length leaf)
- `generation` — low precision (0.2587); high df (286) — in: (not in any accepted-length leaf)
- `4` — low precision (0.2297); high df (283) — in: (not in any accepted-length leaf)
- `conditions` — low precision (0.2615); high df (283) — in: (not in any accepted-length leaf)
- `e.g` — low precision (0.2847); high df (281) — in: (not in any accepted-length leaf)
- `second` — low precision (0.306); high df (281) — in: (not in any accepted-length leaf)
- `us` — low precision (0.2464); high df (280) — in: (not in any accepted-length leaf)
- `response` — low precision (0.2366); high df (279) — in: (not in any accepted-length leaf)
- `made` — low precision (0.259); high df (278) — in: (not in any accepted-length leaf)
- `projects` — low precision (0.2302); high df (278) — in: (not in any accepted-length leaf)
- `known` — low precision (0.2274); high df (277) — in: (not in any accepted-length leaf)
- `broad` — low precision (0.2319); high df (276) — in: (not in any accepted-length leaf)
- `highly` — low precision (0.2572); high df (276) — in: (not in any accepted-length leaf)
- `often` — low precision (0.25); high df (276) — in: (not in any accepted-length leaf)
- `collaboration` — low precision (0.2255); high df (275) — in: (not in any accepted-length leaf)
- `limited` — low precision (0.2945); high df (275) — in: (not in any accepted-length leaf)
- `includes` — low precision (0.3004); high df (273) — in: (not in any accepted-length leaf)
- `dynamics` — low precision (0.2296); high df (270) — in: (not in any accepted-length leaf)
- `environmental` — low precision (0.2074); high df (270) — in: (not in any accepted-length leaf)
- `efforts` — low precision (0.2714); high df (269) — in: (not in any accepted-length leaf)
- `years` — low precision (0.1866); high df (268) — in: (not in any accepted-length leaf)
- `increase` — low precision (0.2547); high df (267) — in: (not in any accepted-length leaf)
- `disease` — high df (266) — in: (not in any accepted-length leaf)
- `programs` — low precision (0.2218); high df (266) — in: (not in any accepted-length leaf)
- `theoretical` — low precision (0.1729); high df (266) — in: (not in any accepted-length leaf)
- `explore` — low precision (0.2453); high df (265) — in: (not in any accepted-length leaf)
- `strategies` — low precision (0.2491); high df (265) — in: (not in any accepted-length leaf)
- `efficient` — low precision (0.2727); high df (264) — in: (not in any accepted-length leaf)
- `applicant` — low precision (0.2099); high df (262) — in: (not in any accepted-length leaf)
- `do` — low precision (0.249); high df (261) — in: (not in any accepted-length leaf)
- `providing` — low precision (0.3218); high df (261) — in: (not in any accepted-length leaf)
- `if` — low precision (0.2538); high df (260) — in: (not in any accepted-length leaf)
- `center` — low precision (0.2412); high df (257) — in: (not in any accepted-length leaf)
- `provided by applicant` — low precision (0.2023); high df (257) — in: (not in any accepted-length leaf)
- `resources` — low precision (0.2257); high df (257) — in: (not in any accepted-length leaf)

... and 1026 more, all in smaller/less-consequential leaves (see outputs/kw_vocab_candidates.json for the full list).

— trust below this line —


## 4. Dropped-as-generic / small-cluster drop candidates

Nothing vanishes silently — every candidate for dropping is listed here with its reason and its terms, so you can override the auto-flag.

- Leaf pre_renumber_1 (3 terms): candidate for drop: cluster below 5-term floor, not yet reviewed
  - terms: should, radical, precisely
- Leaf pre_renumber_4 (2 terms): candidate for drop: cluster below 5-term floor, not yet reviewed
  - terms: interpretation, mine
- Leaf pre_renumber_5 (1 terms): candidate for drop: cluster below 5-term floor, not yet reviewed
  - terms: become
- Leaf pre_renumber_6 (3 terms): candidate for drop: cluster below 5-term floor, not yet reviewed
  - terms: growing, favor, yielding
- Leaf pre_renumber_8 (3 terms): candidate for drop: cluster below 5-term floor, not yet reviewed
  - terms: proximity, minutes, matching
- Leaf pre_renumber_9 (1 terms): candidate for drop: cluster below 5-term floor, not yet reviewed
  - terms: ve
- Leaf pre_renumber_10 (6 terms): candidate for drop: overlaps with leave 11
  - terms: environment, cross-disciplinary, flame, multidisciplinary, fire, pd
- Leaf pre_renumber_18 (2 terms): candidate for drop: cluster below 5-term floor, not yet reviewed
  - terms: higher, ap
- Leaf pre_renumber_22 (2 terms): candidate for drop: cluster below 5-term floor, not yet reviewed
  - terms: alternative, cas
- Leaf pre_renumber_24 (2 terms): candidate for drop: cluster below 5-term floor, not yet reviewed
  - terms: disruption, timing
- Leaf pre_renumber_25 (1 terms): candidate for drop: cluster below 5-term floor, not yet reviewed
  - terms: tracing
- Leaf pre_renumber_23 (Detection & Sensing Systems): Reviewed and rejected: all 20 terms had max_topic_precision <= 0.5 (weakest of any leaf reviewed this session) and their dominant canonical BERTopic classes were scattered across 10+ unrelated domains (Privacy/Cryptography, Cardiac/Neuronal Physiology, Earthquake Engineering, Speech/Autism Communication, Protein Science, Network Science, Conference Travel, Hardware Security, Antimicrobial Ecology, Robotics). This is generic cross-cutting 'detection/accuracy/monitoring' methodology vocabulary (detect, accuracy, identification, comprehensive, characteristics, against, allow, units) that appears across nearly every domain's abstracts, not a coherent topic. The one partial exception, 'sensor technology' (df=7, precision 0.43), leaned toward the Sensor Networks & Energy-Harvesting canonical class already covered by leaf 42 more precisely via 'sensors'/'sensor networks'/'sensing'/'wireless sensor' — not salvaged since it would be a weaker duplicate.

## 5. Leaf keyword lists

### Leaf 0 — Neuroscience & Neural Circuits  (parent: P0)
- keywords: neurons, neuronal, neural circuits, nervous system, synaptic, individual neurons, reconstruction, optogenetic, synapses, dendritic, worm, c elegans, magnetic resonance, fragile x, macular, oxytocin, autism
- ⚠ Genuinely coherent: neurons, neural circuits, synaptic, optogenetic, c. elegans (model organism) all fit. 'image'/'reconstruction'/'mr' read as neuroimaging-adjacent, consistent with the theme.

ADDED (2026-08-30, curation pass closing the no_keyword_evidence unassigned gap): "fragile x", "macular", "oxytocin", "autism" — grant 1163276 (serotonin 5-HT7 agonists in Fragile X syndrome rodent models); grant 523615 (perceptual reorganisation in macular disease); grant 1089127 (Animal Core: oxytocin/birth/epigenetic neural mechanisms); grant 1499383 (Autism Field-Initiated Innovative Research Studies Program). Each df_corpus verified against the real corpus via scripts/_kw_term_df.py (same match_text semantics the classifier itself uses), not guessed.

### Leaf 1 — Molecular & Cellular Biomedicine & Biotechnology  (parent: P0)
- keywords: magnetic resonance, worm, c elegans, biochemical, molecular, cellular, therapeutic, in vivo, proteins, in vitro, signaling, cell, expression, diseases, acid, molecules, inhibition, biomedical imaging, biomedical, charge, fluorescence, iron, absorption, imaging, contrast, optical, resolution, microscopy, sensitivity, characterization, scatter, parp inhibitor, nanoparticle, drug delivery, bone, skeletal, skeleton, fracture, bioethanol, bioprospecting, peptide biosynthesis, osteoblast, persister, pseudomonas aeruginosa, radiotherapy
- ⚠ 641 terms, dominant biomedical cluster — clean, no boundary-fragment pollution remaining. Later enriched with an optical/biomedical-imaging vocabulary set (biomedical imaging, fluorescence, microscopy, contrast, etc.) found while reviewing leaf 16 (Materials Science) — verified via canonical-topic association that these terms genuinely lean biomedical (Cancer & Drug Delivery, Cardiac & Neuronal Physiology, Neuropharmacology) rather than materials/physics, despite superficially reading as optics/physics terms. ADDENDUM (2026-08-29): added 'parp inhibitor', 'nanoparticle', 'drug delivery' (cancer nanoparticle-delivery cluster, e.g. grant 1162069 'PARP Inhibitor Nanotherapy for Ovarian Cancer') and 'bone', 'skeletal' (bone/skeletal-health cluster, e.g. grant 868967 'Kick-starting mechanoadaptation in aged bones') after reviewing Unassigned grants with real text that matched zero curated terms. Also added 'skeleton' and 'fracture' (2026-08-29) after finding 2 bone/skeletal-cluster grants used those words instead of 'bone'/'skeletal' literally (grant 871035 '...appendicular skeleton...', grant 860068 '...fracture healing'). RELABELED (2026-08-29, human decision) from 'Molecular & Cellular Biomedicine' — while reviewing gold-set grant 1035009 ('EFRI 2-DARE: Two-dimensional nanopores with electro-optical control for next generation biotechnological applications'), the friction was that this leaf's existing keyword scope already spans device/application-adjacent content ('nanoparticle', 'drug delivery', 'biomedical imaging', 'parp inhibitor'), not just basic molecular/cellular research — the label just hadn't caught up to that scope. Renamed to make the existing content's real breadth explicit; the keyword list itself is unchanged, so this has zero effect on classification, only on how the leaf reads.

ADDED (2026-08-30, curation pass closing the no_keyword_evidence unassigned gap): "bioethanol", "bioprospecting", "peptide biosynthesis", "osteoblast", "persister", "pseudomonas aeruginosa", "radiotherapy" — grant 625827 (bioethanol via genomics of microbial synergies); grant 1497206 (bioprospecting for industrial enzymes/drug leads); grant 1616677 (plant branched cyclic peptide biosynthesis); grant 1464173 (polyester platform for osteoblast differentiation); grant 684013 (genetics of persister formation in P. aeruginosa); grant 684013 (genetics of persister formation in P. aeruginosa); grant 1161617 (nanocoated brachytherapy spacers for image-guided radiotherapy). Each df_corpus verified against the real corpus via scripts/_kw_term_df.py (same match_text semantics the classifier itself uses), not guessed.

### Leaf 2 — Speech, Hearing & Cognitive Neuroscience  (parent: P0)
- keywords: behavioral, adults, age, older, cochlear implants, dysarthria, phonological, working memory, listening, neurocognitive, auditory, fmri, hearing, asd, alzheimer, neuroimaging, eeg, cognition, brain, attention, individual differences, depth perception
- ⚠ Split out of the original 300-term 'Public & Behavioral Health' leaf (source_leaf_id 7). Coherent speech/hearing/auditory-processing and cognitive-neuroscience vocabulary, including 'worm'/'c elegans' style model-organism and neuroimaging terms consistent with leaf 2's theme (Neuroscience & Neural Circuits) but distinct enough (aging, hearing, speech pathology) to warrant its own leaf. ADDENDUM (2026-08-29): added 'depth perception' after reviewing grant 912670 'Visual Depth Perception from Motion through Texture Accretion and Deletion'.

### Leaf 3 — Public Health Services & Clinical Outcomes  (parent: P1)
- keywords: medicare, cvd, hospital, clinical, patients, public health, chronic, stress, risk, acute, status, burden, death
- ⚠ Slimmed down from the original 300-term 'Public & Behavioral Health' leaf after splitting out three more coherent sub-themes (leaves 27, 28, 29) — see their notes for the split rationale. This residual covers general health-services/clinical-outcomes vocabulary that didn't fit any of the more specific sub-themes; every one of the original top-15 terms was redistributed into the new leaves or rejected as generic, none actually belonged in this residual bucket.

### Leaf 4 — Psychosocial Stress, Trauma & Health Disparities  (parent: P1)
- keywords: immigrants, mpfc, sex-specific, amygdala, ses, fear, ptsd, aggression, victimization, adherence, neonatal, disparities, adolescence, racial, childhood, race, alcohol, child, obesity
- ⚠ Split out of the original 300-term 'Public & Behavioral Health' leaf (source_leaf_id 7) via a recursive sub-clustering pass (k=4 on that leaf's own terms). Coherent grouping of trauma/stress-response vocabulary, its neuroscience substrate (amygdala, mpfc), and social determinants (SES, race, disparities, immigrants).

### Leaf 5 — Digital/Mobile Health & Behavioral Interventions  (parent: P1)
- keywords: health behavior, pa, physical activity, sleep, phone, mental health, just-in-time, app, healthcare, primary care, care, exercise, behavior, interventions, mental, longitudinal, population
- ⚠ Split out of the original 300-term 'Public & Behavioral Health' leaf (source_leaf_id 7). Coherent modern mHealth/behavioral-intervention theme (physical activity, sleep, phone/app-based just-in-time interventions, mental health).

### Leaf 6 — Environmental Health & Ecological Restoration  (parent: P2)
- keywords: natural environment, disturbance, restoration, environmental health, biomonitoring, community engagement core, emerging contaminants, health and justice, srp, srp centers, training core, research translation, core project summary, environmental health sciences, superfund, preterm birth, epa, community engagement, niehs, puerto rico, contaminated, pollution, contaminants, contamination, remediation, exposure, drinking water, administrative core, aerosol, conservation biotechnology
- ⚠ Slimmed down from the original 129-term 'Coastal & Environmental Ecology' leaf after splitting out four more specific sub-themes (leaves 30-33) via recursive sub-clustering (k=6). Was a thin 4-term residual holding general restoration/disturbance-monitoring vocabulary plus 'environmental health' (manually moved here from leaf 14). Later strengthened by merging in a genuine 44-term Environmental Health Sciences & Superfund Research Program cluster discovered while reviewing leaf 14 (EPA/NIEHS-funded Superfund center vocabulary — biomonitoring, contamination, remediation, exposure) — this connects naturally: 'environmental health' was already the anchor term here, and Superfund remediation/contamination-monitoring concepts are a direct match for restoration/ecological-monitoring. Relabeled from 'Environmental Restoration & Ecological Monitoring' to reflect the merged scope. ADDENDUM (2026-08-29): added 'aerosol' after reviewing 2 NOAA atmospheric-chemistry grants (1498542, 1512141, both 'Towards Optimal Configurations of NAQFC Chemistry and Aerosol Representations'). ADDENDUM (2026-08-29): added 'conservation biotechnology' after reviewing grant 1732146 'The Ethics of Conservation Biotechnology: A Conceptual Engineering Approach' — an ethics/humanities grant about biotech tools for ecological conservation, placed here for its conservation/restoration framing rather than Leaf 12 (Social Science).

### Leaf 7 — Predator-Prey & Rocky Intertidal Ecology  (parent: P2)
- keywords: intertidal, predator effects, prey, rocky, predators, predation, reefs, trophic, environmental change, gulf of maine, traits, ecology, gulf, maine, ecological, biodiversity, evolutionary, species, ecosystem, organisms, food, indirect, mathematical models, linkages, productivity, new england, evolution, lobster, estuarine, fisheries
- ⚠ Split out of the original 129-term 'Coastal & Environmental Ecology' leaf (source_leaf_id 11) via recursive sub-clustering (k=6). Coherent food-web/predator-prey ecology theme with a strong Gulf of Maine / New England regional focus. ADDENDUM (2026-08-29): added 'lobster', 'estuarine', 'fisheries' after reviewing Unassigned NOAA fisheries/estuarine grants (e.g. grant 1697213 'The American Lobster Industry...', grant 1697424 'Waquoit Bay National Estuarine Research Reserve') that fit this leaf's existing Gulf of Maine/New England regional-ecology focus but matched zero curated terms.

### Leaf 8 — Ocean Biogeochemistry & Carbonate Chemistry  (parent: P2)
- keywords: calcification, dom, ecosystem services, genetic diversity, marsh, ocean acidification, organic carbon, salt marshes, tide, dissolved organic, organic matter, coral, seawater, dissolved, cycling, marine science, salt, wetlands, nutrient, marine, coastal, coast, seafloor, ocean, nitrogen, sea, earth
- ⚠ Split out of the original 129-term 'Coastal & Environmental Ecology' leaf (source_leaf_id 11) via recursive sub-clustering (k=6). Coherent ocean/marsh biogeochemistry theme (carbonate chemistry, ocean acidification, dissolved organic matter).

### Leaf 9 — Hydrology, Flooding & Watershed Science  (parent: P2)
- keywords: flood risk, floodplain, mississippi river, sedimentary, hydrologic, flood, geomorphic, flooding, earth system, precipitation, hydrology, land use, coastal communities, drainage, streamflow, mississippi, river, hurricane, delta, erosion, sediment, sea level, sedimentation, storm, land, discharge, landscape, environmental engineering, climate change, agricultural, swot
- ⚠ Split out of the original 129-term 'Coastal & Environmental Ecology' leaf (source_leaf_id 11) via recursive sub-clustering (k=6). Coherent surface-hydrology/flood-risk/watershed theme. Also folded in 'environmental engineering', 'climate change', and 'agricultural' from a separate small, mostly-generic sub-cluster (group 5) that fit this theme better than standing alone.

ADDED (2026-08-30, curation pass closing the no_keyword_evidence unassigned gap): "swot" — grant 1758129 (harnessing SWOT satellite observations for well-water disaster surveillance). Each df_corpus verified against the real corpus via scripts/_kw_term_df.py (same match_text semantics the classifier itself uses), not guessed.

### Leaf 10 — Groundwater/Soil Chemistry & Water Quality  (parent: P2)
- keywords: electrolysis, sodium, coal, north carolina, water quality, soil
- ⚠ Split out of the original 129-term 'Coastal & Environmental Ecology' leaf (source_leaf_id 11) via recursive sub-clustering (k=6). Distinct from surface hydrology (leaf 32) — groundwater/soil geochemistry and water-quality vocabulary. CORRECTION (2026-08-29, found during a negative-centroid-margin review): removed 'wells' — its plural-fold stem match ('wells'->'well') was colliding with the common English adverb 'well' ('as well', 'well-known'), matching ~42 of this leaf's 86 assigned grants purely via that collision (e.g. an Osteoarthritis study, a Fermi-level condensed-matter physics grant, a satellite-servicing SBIR — none groundwater-related). Also removed 'water', 'oxygen', 'carbon', 'gas', 'ph', 'bubbles', 'saturation', 'saturated' — all individually too generic (common across biology/chemistry/materials science broadly), confirmed by inspecting this leaf's actual member grants: the real, on-theme matches (well-water contamination, soil remediation, liquefaction/geotechnical engineering, coal-ash groundwater impact) cluster at high confidence via 'water quality', 'north carolina', 'coal', 'sodium', 'electrolysis', 'soil' instead — those 6 terms are the leaf's real signal, kept. 'saturation'/'saturated' specifically also collide with an unrelated sense (color saturation in vision science).

### Leaf 11 — Conference & Student Travel Awards  (parent: P7)
- keywords: attend, student travel, travel, students to attend, acm, attending, present their work, travel support, provides travel, travel funds, opportunity to present, leading-edge research, student travel grant, venue, conference, international symposium
- ⚠ 93 terms, the NSF conference/travel-funding-instrument theme found independently by both Plan A and Plan B during discovery — a real, distinct funding-mechanism cluster, not noise. Checked for sub-themes via recursive sub-clustering (k=2 best silhouette, 0.19): the split found is just 'student-travel-specific phrasing' vs. 'general conference logistics + noise', not two genuinely distinct subjects — kept as one leaf. Scanning the full 93-term candidate pool (beyond the current top-15) turned up bare calendar years/months as candidate terms — pure scheduling noise, never present in the active keyword list but recorded in rejected_terms for the audit trail since we specifically found and considered them.

ADDED (2026-08-30, curation pass closing the no_keyword_evidence unassigned gap): "international symposium" — grant 878888 (International Symposium for Polymer Electrolytes, Iceland). Each df_corpus verified against the real corpus via scripts/_kw_term_df.py (same match_text semantics the classifier itself uses), not guessed.

### Leaf 12 — Social Science & Public Policy  (parent: P3)
- keywords: stakeholders, policy, government, organizations, economic, urban, society, researchers, needs, social science, public, law, agencies, social, labor, political, management, oral history, digital humanities, humanities, manuscripts, youth
- ⚠ Slimmed down from the original 189-term leaf after splitting out two genuinely distinct sub-themes: leaf 34 (Security, Trafficking, Public Health Crisis & Disaster Resilience) and a corrected leaf 26 (Education, Games & Informal STEM Learning — leaf 26 had previously been mistakenly populated with leaf-14's terms instead of its own real content). At k=2 the original 189 terms split entirely between those two groups with no natural third residual, so this leaf keeps the generic-but-real policy/stakeholder/governance vocabulary salvaged from both groups' low-precision tails — genuine content, just not specific enough to belong to either narrower theme. ADDENDUM (2026-08-29, human-curated post-promotion): added 'oral history' (df_corpus=1) and 'digital humanities' (df_corpus=3) after reviewing an Unassigned grant with real abstract text ('Visualizing Oral Histories of Bengal using Digital Humanities Tools', grant_id 726280) that matched zero curated terms anywhere in the taxonomy. Verified against the corpus before adding: both terms are highly specific (df_corpus 1 and 3), and the 'digital humanities' addition also corrects a real misclassification found in the same review — grant 1619895 ('Re-establishing and Sustaining a Working Ecology for Digital Humanities Scholarship') was landing in the Predator-Prey & Rocky Intertidal Ecology leaf via 'ecology' used metaphorically, not literally. ADDENDUM (2026-08-29): added 'humanities' and 'manuscripts' after reviewing Unassigned NEH-funded humanities grants (e.g. grant 1148978 'Space, Place, and the Humanities', grant 1080743 'Analyzing Ojibwe and Cherokee Manuscripts') that matched zero curated terms; also strengthens the earlier 'oral history'/'digital humanities' addition's coverage of this same broad theme. ADDENDUM (2026-08-29): added 'youth' after reviewing grant 993053 'Utah Transition Youth Empowered to Succeed (UT YES)' (HHS youth-empowerment/transition services).

### Leaf 13 — Faculty Development, Diversity & Institutional Partnerships  (parent: P7)
- keywords: faculty, professional development, professional, leadership, institutions, urm, recruitment, diverse, mentor, partnership, career, college, fellowship, graduate research fellowship, fellowship program grfp, lsamp, entrepreneurship, stem, stem faculty, stem education, retention, mentoring, women, minority, gender, female, black, doctoral, scholars, research experiences, graduate education, trainees, training program, universities, diversity, traineeship, inbre
- ⚠ 172 terms. Checked via recursive sub-clustering (k=2): split into this leaf's real 128-term content (enriched below) and a genuinely distinct 44-term Environmental Health Sciences & Superfund Research Program cluster, now merged into leaf 11 (Environmental Health & Ecological Restoration) instead — 'environmental health' was the anchor term of that real cluster, not a lone stray outlier as first thought. ADDENDUM (2026-08-29): added 'traineeship' after reviewing Unassigned graduate traineeship-award grants (e.g. grant 1546186 'Graduate Traineeship Award for Matthew Schinault') — a better fit here (alongside existing 'fellowship'/'trainees'/'training program') than Leaf 11's travel-specific scope.

ADDED (2026-08-30, curation pass closing the no_keyword_evidence unassigned gap): "inbre" — grant 1250146 (UNM Mass Spectrometry Core Facility, an NIH IDeA/INBRE network grant). Each df_corpus verified against the real corpus via scripts/_kw_term_df.py (same match_text semantics the classifier itself uses), not guessed.

### Leaf 14 — Education, Games & Informal STEM Learning  (parent: P3)
- keywords: computational thinking, science learning, student learning, learners, learning tools, stem learning, systems thinking, learning activities, curricula, science education, classroom, education researchers, enable students, game design, instructors, curriculum, pedagogy, multimedia, broadening participation, learning environment, workshops, teaching, informal, modules, education, teach, workforce, virtual, thinking, gaming, mixed reality, reu, erc, education program, engineering research, hands-on, teachers, middle school, middle school students, underrepresented, graduate students, high school, foreign language, online laboratory
- ⚠ CORRECTED: this leaf was previously mistakenly populated with terms copied from leaf 14 (faculty, institutions, urm, academic, diverse, mentor, college) instead of its own real content — none of those actually relate to education/games. Re-derived from a recursive sub-clustering pass on leaf 13 (k=2), which surfaced a genuine 101-term education/learning theme. Curated down to the specific, unambiguous terms; kept 'mixed reality' from the earlier manual addition. Deliberately excludes bare 'game' (verified polysemous — game theory in economics/networking, media/labor studies of gaming, not just educational games) in favor of the safer compound 'game design'. 'gaming' is intentionally also added to leaf 20 (Software Systems) since its 6 real occurrences split genuinely between education and software-infrastructure senses. Later enriched with STEM-education/outreach-program vocabulary (reu, erc, teachers, middle school, underrepresented, graduate students, high school) found while reviewing leaf 16 (Materials Science) — this is broader-impacts/outreach-participant language distinct in kind from this leaf's original learning-science content, but folded in here rather than fragmenting into yet another education-adjacent leaf. ADDENDUM (2026-08-29): added 'foreign language' after reviewing grant 43588 'Undergraduate International Studies and Foreign Language Programs' — a thin, single-grant addition; note the leaf's label (STEM/games/informal learning) doesn't perfectly describe language-program content, kept here per human decision as the closest 'undergraduate learning' home.

ADDED (2026-08-30, curation pass closing the no_keyword_evidence unassigned gap): "online laboratory" — grant 791101 (creating an online laboratory). Each df_corpus verified against the real corpus via scripts/_kw_term_df.py (same match_text semantics the classifier itself uses), not guessed.

### Leaf 15 — Security, Trafficking, Public Health Crisis & Disaster Resilience  (parent: P3)
- keywords: human trafficking, illicit supply networks, interdiction, trafficking networks, victims, illicit, covid-19, shortages, debris, illegal, law enforcement, infectious disease, pandemic, governance, disposal, trafficking, enforcement, natural disasters, distribution systems, shelter, criminal, survivors, crime, epidemic, infectious, crisis, influenza, supply chain, resilience, justice, preparedness, resilient, hazards
- ⚠ Split out of the original 189-term 'Social Science & Public Policy' leaf (source_leaf_id 13) via recursive sub-clustering (k=2). Genuinely distinct theme spanning human trafficking/illicit networks, infectious-disease crisis response (covid-19, pandemic, epidemic), and natural-disaster resilience — nothing to do with either generic social-science policy or education.

### Leaf 16 — Civil & Earthquake Engineering  (parent: P4)
- keywords: steel, earthquake, collapse, earthquake engineering, performance-based, existing structures, full-scale, neesr, seismic, structural systems, nees, wind, civil, earthquake hazards, natural hazards, offshore wind energy, wind energy, turbine, offshore, structural health monitoring, renewable energy sources, energy sources, highway, power systems, infrastructure systems, civil infrastructure, grid
- ⚠ 46 terms. Checked via recursive sub-clustering (k=3): found two small (8- and 12-term) sub-groups (offshore wind energy; infrastructure monitoring/smart grid) but both too thin to justify their own leaves at this scale, so their genuinely specific terms were folded in here instead rather than fragmenting into new leaves. Verified 'wind' (bare) via document context — genuinely splits between wind-hazards-on-structures (kept here) and wind-energy/turbines (also relevant here since offshore wind engineering was folded in) — no conflict. Verified and REJECTED bare 'health monitoring' after checking context: majority of its real occurrences are about patient/personal health monitoring (wearables, biosensing), not structural — kept the unambiguous compound 'structural health monitoring' instead.

### Leaf 17 — Materials Science & Nanotechnology  (parent: P4)
- keywords: materials, temperature, thermal, films, nanostructures, thin, fabrication, semiconductor, nanoscale, spin, microwave, high-efficiency, nanomanufacturing, tunable, heat, electronic, magnetic, electric, composite, conduction, nanotechnology, manufacturing, electrical, demonstration, energy, multi-scale, solidification, alloy, qubit, quantum phases, solid-state batteries, fullerene, permanent magnets, origami, ionomer, neutron reflectivity, raman spectroscopy, nexafs, metal-c60, cnt-modified, afm-raman
- ⚠ Checked via recursive sub-clustering (k=5) on the full 132-term cluster. Found 4 sub-groups beyond the real materials-science core: an optical/biomedical-imaging group (moved to leaf 3 after checking canonical-topic associations confirmed it's genuinely biomedical, not materials), a very clean Gravitational Wave/LIGO instrumentation group (split to a new leaf), a STEM-education/outreach-program group (strong terms moved to leaf 26, weak ones rejected — this leaf should hold materials-science CONTENT, not broader-impacts language, so 'high school'/'outreach' were removed despite an earlier note calling them consistent), and a generic cross-cutting methodology group (mostly rejected). This leaf now holds only the genuine materials/nanotech core. ADDENDUM (2026-08-29): added 'solidification' and 'alloy' after reviewing Unassigned grants about alloy-solidification microstructure modeling (e.g. grant 1316012, 'Phase-Field Modeling of Solidification Microstructures') that matched zero curated terms despite being a clear materials-science fit. ADDENDUM (2026-08-29): added 'qubit' and 'quantum phases' after reviewing 2 Unassigned quantum-devices grants (1393768 'Design, Control and Application of Next-Generation Qubits', 544966 'Novel Quantum Phases at Interfaces') — a third candidate (1777815, 'Quantum Theory and Measured Turnover Rates...') was judged too ambiguous (really catalysis/chemistry, not quantum devices) and deliberately left Unassigned rather than force-fit.

ADDED (2026-08-30, curation pass closing the no_keyword_evidence unassigned gap): "solid-state batteries", "fullerene", "permanent magnets", "origami", "ionomer", "neutron reflectivity", "raman spectroscopy", "nexafs" — grant 1730685 (Li-ion sulfide-based all-solid-state batteries); grant 1315237 (interfacial phenomena, noble metal-C60 interaction); grant 727353 (rare-earth-free permanent magnets); grant 1471140 (rigidity-tuned elastomer origami tessellations); grant 878820 (ionomer-metal interfacial structure); grant 878820 (ionomer-metal interfacial structure); grant 1778141 (tip-enhanced AFM-Raman spectroscopy); grant 544819 (electrochemical/NEXAFS analysis of adsorbates). Each df_corpus verified against the real corpus via scripts/_kw_term_df.py (same match_text semantics the classifier itself uses), not guessed.

FIXUP (2026-08-30): added "metal-c60" — grant 1315237 (noble metal-C60 interaction) — 'fullerene' was an external-knowledge synonym not literally in the title (and 'c60' alone can't match either, since the hyphen bridges it into one token 'metal-c60'); using the actual literal token.

FIXUP (2026-08-30): added "cnt-modified" — grant 1570580 (bio-inspired CNT-modified hierarchical/fractal interfaces) — no term was added for this grant in the first curation pass; using the literal hyphen-bridged token.

FIXUP (2026-08-30): added "afm-raman" — grant 1778141 (tip-enhanced AFM-Raman spectroscopy) — 'raman spectroscopy' can't match because the hyphen bridges 'afm' and 'raman' into one token 'afm-raman', so bare 'raman' never appears as its own token; using the literal token.

### Leaf 18 — Algebra, Geometry, Mathematical Physics & Metascience  (parent: P5)
- keywords: categorical, cluster algebras, cohomology, commutative, elliptic, integrable systems, maurice auslander, noncommutative, noncommutative algebra, poisson, quantum groups, string theory, symplectic, algebras, representation theory, areas of mathematics, algebraic geometry, invariant theory, singularities, quiver, invariants, combinatorics, algebraic, manifolds, mathematicians, singular, gauge, lie, geometric, theorem, geometry, homology, woods hole, combinatorial, categories, topological, mathematics, topology, differential, scientific success, scientific performance
- ⚠ MAJOR FIX: 'uncertainty', 'inference', 'bayesian', 'algorithms', 'probabilistic' were mistakenly present in this leaf's keywords — checked the original frozen discovery artifact (kw_term_groups_planB.json's L17 top_terms) and confirmed those 5 terms never belonged here at all; they're genuine leaf-19 (Control Systems/CPS/ML) content that got mixed in, the same class of bug as leaf 26's earlier copy-paste error. Also checked via recursive sub-clustering (k=2, exceptionally high silhouette 0.317 — one of the cleanest splits found this session): the remaining 125 terms split cleanly into this leaf's real algebra/geometry/mathematical-physics core (93 terms, curated below) and a completely distinct Particle & High-Energy Physics theme (32 terms, split to a new leaf) that happened to share embedding-space proximity via string-theory/symmetry vocabulary. RELABELED (2026-08-29, human decision) from 'Algebra, Geometry & Mathematical Physics' after adding 'scientific success' and 'scientific performance' to cover 2 Unassigned AFRL metascience/scientometrics grants (1571021 'The fundamentals of predictability of scientific success', 1570796 'Quantifying Scientific Performance and Success in the Physics Community') — a niche, quantitative/statistical subfield that doesn't fit any other leaf, placed here as the closest quantitative-methods home.

### Leaf 19 — Particle Physics & High-Energy Physics  (parent: P5)
- keywords: extra dimensions, higgs, higgs boson, new physics, quark, standard model, supersymmetry, theorynet, particle physics, lhc, large hadron collider, dark matter, cern, collider, hadron, universe, cms, extra, dark, high energy, symmetry, particle, elementary, lsst
- ⚠ Split out of the original 125-term 'Algebra, Geometry & Mathematical Physics' leaf (source_leaf_id 17) via recursive sub-clustering (k=2, silhouette 0.317 — one of the cleanest splits found this session; several terms have perfect 1.0 precision). Genuinely distinct experimental/theoretical particle physics (CERN, LHC, Higgs boson, dark matter, standard model, supersymmetry) — shares embedding-space proximity with pure algebra/geometry only via string-theory/symmetry vocabulary, but is a completely different research community.

ADDED (2026-08-30, curation pass closing the no_keyword_evidence unassigned gap): "lsst" — grant 1729903 (commissioning robust analysis tools for LSST DESC). Each df_corpus verified against the real corpus via scripts/_kw_term_df.py (same match_text semantics the classifier itself uses), not guessed.

### Leaf 20 — Gravitational Wave Detection & Observational Astrophysics  (parent: P5)
- keywords: a+, advanced ligo, astrophysics, ccr, cosmic, gravitational wave, ligo, mirror coatings, thermal noise, gravitational, amorphous, hole, astronomy, mirror, detector, dissipation, coatings, numerical simulation, xmm-newton, tidal disruption, super-eddington, gamma-ray, antimatter, cosmology, prototype flight
- ⚠ Split out of the original 132-term 'Materials Science & Nanotechnology' leaf (source_leaf_id 16) via recursive sub-clustering (k=5). Exceptionally clean, tight cluster — 9 of 18 kept terms have perfect 1.0 precision. Genuinely a distinct physics/astrophysics instrumentation area (LIGO mirror-coating materials research, gravitational-wave detector thermal noise), not general materials science. Parented under P5 (Materials Science & Structural/Civil Engineering) since mirror-coating research is fundamentally materials science applied to detector optics — a judgment call, revisit if a better-fitting parent becomes available. RELABELED (2026-08-29, human decision) from 'Gravitational Wave Detection & LIGO Instrumentation' after adding 'xmm-newton', 'tidal disruption', 'super-eddington' to cover a 10-grant NASA X-ray-astronomy/tidal-disruption-event research program (e.g. grant 1326694 'Understanding the Nature of XMM-Newton Serendipitous X-Ray Sources') that had no home — observational X-ray astrophysics sits naturally alongside this leaf's existing gravitational-wave/LIGO instrumentation scope.

ADDED (2026-08-30, curation pass closing the no_keyword_evidence unassigned gap): "gamma-ray", "antimatter", "cosmology" — grant 1720106 (GRAMS gamma-ray/antimatter survey balloon mission); grant 1720106 (GRAMS gamma-ray/antimatter survey balloon mission); grant 1721044 (galaxy intrinsic alignments for cosmology, Roman Space Telescope). Each df_corpus verified against the real corpus via scripts/_kw_term_df.py (same match_text semantics the classifier itself uses), not guessed.

FIXUP (2026-08-30): added "prototype flight" — grant 1720106 (GRAMS project) — 'gamma-ray'/'antimatter' were external-knowledge terms not literally present in the title; replaced with the doc's own literal text after the first attempt failed to match.

### Leaf 21 — Control Systems, Cyber-Physical Systems & Machine Learning  (parent: P6)
- keywords: nonlinear control, dnn, robust control, computationally tractable, dnns, distributed optimization, state estimation, systems theory, reinforcement learning, control systems, analysis and design, training data, data driven, descent, cyber-physical systems, fragility, optimal control, sparse, optimization algorithms, computationally efficient, vision, cyber-physical, bayesian, uncertainty, control theory, algorithms, deep learning, dynamical systems, neural networks, machine learning, inference, classify, optimization, asynchronous, decentralized, probabilistic, distributed algorithms, stochastic, classification, facial, anomaly detection, natural language processing, transfer learning, cortical column, terrain estimation, task learning, systems/machine
- ⚠ Checked via recursive sub-clustering (k=2, silhouette 0.229): found a genuinely distinct 41-term Rehabilitation Robotics & Assistive Technology theme (split to a new leaf — this echoes a very similar cluster seen once before in the original Plan A discovery data, suggesting it's a real, recurring NEU research area) and confirmed/enriched this leaf's real control-theory/CPS/ML core with the remaining 73-term group. ADDENDUM (2026-08-29): added 'anomaly detection', 'natural language processing', 'transfer learning' after reviewing a cluster of military-funded (ARO/AFRL) AI/ML Unassigned grants (e.g. grant 1789375 'Explainable Deep Anomaly Detection', grant 913696 'Sociolinguistically Informed NLP') that matched zero curated terms despite clearly belonging in this leaf's ML scope. ADDENDUM (2026-08-29): added 'cortical column' after reviewing grant 1570775 'Principles of Robust Learning Derived from the Structure and Function of the Cortical Column' — a neuroscience-inspired ML grant, judged ML-focused. ADDENDUM (2026-08-29): added 'terrain estimation' after reviewing grant 1563570 'Coordinated Multi-Robot-Chain for Terrain Estimation and Exploration' — field-robotics/multi-robot coordination, not civil/structural engineering despite the 'terrain' wording; a better fit here than Leaf 16 (Civil & Earthquake Engineering).

ADDED (2026-08-30, curation pass closing the no_keyword_evidence unassigned gap): "dynamical systems", "task learning" — grant 1570983 (dynamical systems/machine learning approach to data deluge); grant 1777764 (procedural task learning from goal-oriented activity data). Each df_corpus verified against the real corpus via scripts/_kw_term_df.py (same match_text semantics the classifier itself uses), not guessed.

### Leaf 22 — Programming Languages & Software Engineering  (parent: P6)
- keywords: java, software contracts, type systems, typed, software engineers, javascript, contracts, program analysis, software developers, bugs, compiler, racket, programmers, programming languages, compilation, formal verification, compiled, formal methods, gradual, scripting, software components, software systems, low-level, concurrent, correctness, design-time, semantics, verification, verified, developers, execution, code, formal, abstraction, static, software engineering, high-level, open-source, programming, run-time, errors, open-source software, software, gaming, vertica
- ⚠ RELABELED (was 'Software Systems & Cybersecurity'): checked via recursive sub-clustering (k=5) on the full 284-term cluster — the single biggest leaf reviewed this session. Found 4 genuinely distinct real themes: this leaf's real core (programming languages/software engineering — matches the original 'software'/'code'/'developers'/'open-source' keywords much better than 'cybersecurity' did), plus Cryptography & Hardware Security, Computer Architecture & High-Performance Computing, and Theoretical CS/Network/Data Science (all split to new leaves), plus one weak/generic bucket (mostly rejected, 'mobile devices'/'mobile' moved to leaf 21 instead). Cross-checked all 4 real groups against leaves 19/21/23's full underlying clusters and confirmed zero term-level overlap — Plan B's discovery clustering assigns each term to exactly one base cluster, so duplication only ever comes from manual curation mistakes (like the ones already found and fixed in leaves 17/26), not independent rediscovery. Also added 'gaming' here (see leaf 26's notes — its 6 real occurrences split genuinely between education and software-infrastructure senses).

ADDED (2026-08-30, curation pass closing the no_keyword_evidence unassigned gap): "vertica" — grant 1616520 (Vertica 2.0: transitioning the Stubbifier tool). Each df_corpus verified against the real corpus via scripts/_kw_term_df.py (same match_text semantics the classifier itself uses), not guessed.

### Leaf 23 — Wireless Communications, Antennas & Electromagnetic Metamaterials  (parent: P6)
- keywords: 60 ghz, cellular networks, mmwave, pawr, ultra-broadband, wireless research, 5g, thz, 6g, mimo, data rates, ghz, wireless networking, wi-fi, terahertz, wireless systems, physical layer, software-defined, radio, cross-layer, wireless networks, wireless, stack, programmable, testbed, bandwidth, spectrum, channel, transmission, connectivity, networking, experimentation, cns, layer, traffic, routing, coding, mobility, nodes, networked, allocation, delay, on-demand, scheduling, mobile devices, mobile, antenna, nanoantenna
- ⚠ Restructured from the original 211-term 'Wireless Networking & Embedded Systems' leaf via recursive sub-clustering. Split off leaf 41 (Underwater Acoustic Communications & Marine Robotics, a fully distinct theme) and, within the remaining 164-term core, further sub-sub-clustered (k=5, silhouette 0.208) into: this leaf's 5G/mmWave/cellular core (subgroup 3, cleanest/highest-precision group), new leaf 42 (Energy Harvesting & Low-Power RF/Wireless Sensors, subgroup 1), new leaf 43 (IoT & Embedded Systems, subgroup 4), plus two mostly-generic subgroups (2: NSF tech-transfer boilerplate; 5: generic networking words) that were mostly rejected, with a handful of genuinely networking-specific terms (routing, coding, mobility, etc.) salvaged into this leaf. Retains 'mobile'/'mobile devices' salvaged earlier from leaf 20's review. RELABELED (2026-08-29, human decision) from '5G/mmWave & Cellular Wireless Communications' after adding 'antenna' and 'nanoantenna' to cover 4 Unassigned ONR/AFRL antenna/metamaterial-engineering grants (e.g. 727523 'Transformative Parameters Extreme Antennas...', 1549255 'Hybrid Graphene/Semiconductor...Nano-antenna for Terahertz-band Communication'). Some of these lean more classical-EM/materials than 5G/cellular communications specifically — kept here rather than split out, a deliberate human call given the small size of the cluster.

### Leaf 24 — Rehabilitation Robotics & Assistive Technology  (parent: P6)
- keywords: gait, human-robot, knee, robots, rehabilitation, locomotion, stroke, assistive, robotics, walking, intent, motor, manipulation, limb, intuitive, disabilities, assistance, neurological, movement, coordination, hand, injury, stimulation
- ⚠ Split out of the original 114-term 'Control Systems, Cyber-Physical Systems & Machine Learning' leaf (source_leaf_id 19) via recursive sub-clustering (k=2, silhouette 0.229). Genuinely distinct biomedical/healthcare-robotics theme — gait/locomotion rehabilitation, stroke recovery, assistive devices, human-robot interaction for disability support. This echoes a very similar cluster seen once before, independently, in the original Plan A discovery data — suggesting it's a real, recurring NEU research area, not an artifact of this particular clustering run.

### Leaf 25 — Cryptography & Hardware Security  (parent: P6)
- keywords: fully homomorphic encryption, homomorphic, side-channel attacks, system security, information leakage, encryption, differential privacy, encrypted, hardware security, side-channel, sensitive data, communication protocols, reverse engineering, secure computation, cryptographic, attack surface, defenses, leakage, cryptography, privacy-preserving, security and privacy, auditing, authentication, countermeasures, defensive, attackers, trusted, twc, networking protocols, privacy, security guarantees, adversarial, assurance, cyber, cybersecurity, malware, trustworthy, compromised, confidentiality, verifiable, security, attacks, malicious, adversaries, secure
- ⚠ Split out of the original 284-term 'Software Systems & Cybersecurity' leaf (source_leaf_id 20) via recursive sub-clustering (k=5). Very clean, high-precision crypto/hardware-security theme — homomorphic encryption, side-channel attacks, differential privacy, hardware security. Cross-checked against leaves 19/21/23's full underlying clusters: zero term-level overlap.

### Leaf 26 — Computer Architecture & High-Performance Computing  (parent: P6)
- keywords: i/o, distributed systems, ndn, virtualization, caching, computer architecture, gpus, hpc, performance and reliability, gpu, storage systems, computing infrastructure, data centers, threads, high performance computing, cpu, cache, disk, acceleration, computing resources, cloud, heterogeneous, computing platforms, computing systems, cyberinfrastructure, application-specific, storage, high performance, cloud computing, computing, computer systems, workload
- ⚠ Split out of the original 284-term 'Software Systems & Cybersecurity' leaf (source_leaf_id 20) via recursive sub-clustering (k=5). Distributed systems, virtualization, GPUs/HPC, cloud/data-center infrastructure. Cross-checked against leaves 19/21/23's full underlying clusters: zero term-level overlap.

### Leaf 27 — Theoretical CS, Network & Data Science  (parent: P6)
- keywords: complex networks, complexity theory, group theory, randomness, bounds, lower bounds, network dynamics, network analysis, network science, databases, retrieval, queries, graph, algorithmic, data science, computer science, social networks, data analysis, data-intensive, data mining, complexity, computational complexity, collaboration networks, online collaboration, interpretability, subset selection, counterfactuals, data selection
- ⚠ Split out of the original 284-term 'Software Systems & Cybersecurity' leaf (source_leaf_id 20) via recursive sub-clustering (k=5). Real but noisier signal than the other splits (only ~22 of 85 original terms were genuinely specific — the worst signal-to-noise ratio of any leaf reviewed this session). Note: uses 'network' in the graph-theory/social-network-analysis sense (network science, network dynamics), distinct from leaf 21's 'wireless networking' (physical/radio communications) — different fields sharing a word, not a duplicate theme; cross-checked and confirmed zero term-level overlap with leaf 21's full cluster. ADDENDUM (2026-08-29): added 'collaboration networks' and 'online collaboration' after reviewing 2 Unassigned grants about online/large-scale collaboration in networks (grants 1153671, 1153510) that fit this leaf's existing network-science scope but matched zero curated terms. Both terms are currently singleton matches (df_corpus=1) — narrow, but real and unambiguous.

ADDED (2026-08-30, curation pass closing the no_keyword_evidence unassigned gap): "interpretability", "subset selection", "counterfactuals", "data selection" — grant 1777587 (neural models for text: efficiency, interpretability, accuracy); grant 1548072 (sequential multi-modal subset selection framework); grant 1153510 (large scale networks and unobservable counterfactuals); grant 1776975 (efficient and coherent data selection and summarization). Each df_corpus verified against the real corpus via scripts/_kw_term_df.py (same match_text semantics the classifier itself uses), not guessed.

### Leaf 28 — Underwater Acoustic Communications & Marine Robotics  (parent: P6)
- keywords: acoustic communications, acoustic waveguide remote, autonomous underwater vehicles, marine mammal, modems, ocean acoustic, ocean acoustic waveguide, underwater acoustic, underwater communication, underwater networking, underwater networks, vehicles auvs, waveguide remote sensing, autonomous underwater, underwater vehicles, acoustic data, whoi, acoustic sensing, underwater, auv, waveguide, oceanographic, mac, mammals, vocalizations, acoustic
- ⚠ Split out of leaf 21 (Wireless Networking) via recursive sub-clustering (k=2, silhouette 0.246) — a genuinely distinct theme (acoustic modems, AUVs, underwater networking/MAC protocols, WHOI) unrelated to terrestrial/cellular wireless. Checked against leaf 32 (Hydrology, Flooding & Watershed Science) for a possible merge given the shared 'water' surface similarity; rejected — only 19% doc overlap (11/58), driven by incidental generic terms, and this cluster split out of the wireless-networking leaf (engineering/comms) not the environmental-science leaf split that produced leaf 32 (earth-science/watershed) — different research communities despite the shared medium.

### Leaf 29 — Energy Harvesting & Low-Power RF/Wireless Sensors  (parent: P6)
- keywords: zero-power, near-zero, rfid, wireless sensor networks, rf, ultra-low power, wireless sensor, energy harvesting, harvest, harvesting, receiver, interference, power consumption, beamforming, piezoelectric, sensors, ultra-low, sensor networks, localization, sensing, signal, signal processing, frequency, passive, filtering
- ⚠ Split out of leaf 21's 164-term wireless-networking core via sub-sub-clustering (k=5, silhouette 0.208, subgroup 1). A real, distinct research niche — RFID/backscatter, ultra-low-power sensor design, piezoelectric/RF energy harvesting — separate from the 5G/cellular core (leaf 21) and IoT/embedded systems (leaf 43).

### Leaf 30 — IoT & Embedded Systems  (parent: P6)
- keywords: safety and security, iot systems, embedded, latency, internet-of-things, embedded systems, iot devices, system-level, architecture, fpga, iot, hardware and software
- ⚠ Split out of leaf 21's 164-term wireless-networking core via sub-sub-clustering (k=5, silhouette 0.208, subgroup 4). Smallest/weakest-precision of the three new splits but coherent (IoT devices/systems, embedded systems, FPGA, hardware-software co-design). Checked against leaf 19 (Control Systems, Cyber-Physical Systems & Machine Learning) for overlap — leaf 19's keyword list has zero embedded/IoT/hardware vocabulary, confirming this is a distinct theme, not duplicated content.


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


## 8. The 20 largest currently-Unassigned grants by dollars (of 36 total, source: keyword classifier)

| grant_id | title | dollars |
|---|---|---|
| 78396 | Grant | $6,750,000 |
| 78580 | Grant | $2,125,417 |
| 77712 | Grant | $1,890,287 |
| 574449 | Grant | $1,215,103 |
| 77710 | Grant | $840,000 |
| 77711 | Grant | $840,000 |
| 1113526 | Pilot-Project-Core | $821,632 |
| 78790 | Grant | $791,937 |
| 78395 | Grant | $625,780 |
| 77713 | Grant | $598,000 |
| 80933 | Grant | $499,851 |
| 76517 | Grant | $462,717 |
| 78577 | Grant | $443,146 |
| 591780 | EVALUATION OF THE 'REWARDING RESULTS' PROGRAM | $431,463 |
| 79921 | Grant | $385,521 |
| 75903 | Grant | $362,003 |
| 80712 | Grant | $345,173 |
| 79920 | Grant | $329,933 |
| 79919 | Grant | $327,000 |
| 80714 | Grant | $299,990 |