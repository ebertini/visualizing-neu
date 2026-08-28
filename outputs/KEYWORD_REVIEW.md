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

Sorted so terms sitting inside a large (>=50-term, likely-accepted) leaf come first — those are the ones actually worth your time.

— review these; everything else can be skimmed —

- `researchers` — low precision (0.25); high df (484) — in: leaf 13 (189 terms)
- `fundamental` — low precision (0.2362); high df (453) — in: leaf 16 (132 terms)
- `materials` — high df (353) — in: leaf 16 (132 terms)
- `outreach` — low precision (0.243); high df (321) — in: leaf 16 (132 terms)
- `social` — low precision (0.2866); high df (321) — in: leaf 13 (189 terms)
- `diverse` — low precision (0.2437); high df (316) — in: leaf 14 (172 terms)
- `framework` — low precision (0.273); high df (315) — in: leaf 19 (114 terms)
- `cell` — low precision (0.3137); high df (306) — in: leaf 3 (641 terms)
- `algorithms` — low precision (0.3115); high df (305) — in: leaf 19 (114 terms)
- `molecular` — low precision (0.3108); high df (296) — in: leaf 3 (641 terms)
- `software` — low precision (0.2576); high df (295) — in: leaf 20 (284 terms)
- `highly` — low precision (0.2572); high df (276) — in: leaf 16 (132 terms)
- `environmental` — low precision (0.2074); high df (270) — in: leaf 11 (129 terms)
- `factors` — low precision (0.2638); high df (254) — in: leaf 7 (300 terms)
- `build` — low precision (0.251); high df (251) — in: leaf 13 (189 terms)
- `life` — low precision (0.2438); high df (242) — in: leaf 7 (300 terms)
- `building` — low precision (0.3195); high df (241) — in: leaf 13 (189 terms)
- `security` — low precision (0.3288); high df (219) — in: leaf 20 (284 terms)
- `examine` — low precision (0.1806); high df (216) — in: leaf 7 (300 terms)
- `findings` — low precision (0.2105); high df (209) — in: leaf 7 (300 terms)
- `issues` — low precision (0.2885); high df (208) — in: leaf 13 (189 terms)
- `whether` — low precision (0.1942); high df (206) — in: leaf 7 (300 terms)
- `career` — low precision (0.2); high df (205) — in: leaf 14 (172 terms)
- `power` — low precision (0.2414); high df (203) — in: leaf 21 (211 terms)
- `robust` — low precision (0.2525); high df (202) — in: leaf 19 (114 terms)
- `society` — low precision (0.2871); high df (202) — in: leaf 13 (189 terms)
- `needs` — low precision (0.2714); high df (199) — in: leaf 13 (189 terms)
- `population` — low precision (0.2576); high df (198) — in: leaf 7 (300 terms)
- `cellular` — low precision (0.2708); high df (192) — in: leaf 3 (641 terms)
- `proteins` — high df (183) — in: leaf 3 (641 terms)
- `faculty` — low precision (0.2818); high df (181) — in: leaf 14 (172 terms)
- `high school` — low precision (0.2597); high df (181) — in: leaf 16 (132 terms)
- `institutions` — low precision (0.2222); high df (180) — in: leaf 14 (172 terms)
- `tasks` — low precision (0.3218); high df (174) — in: leaf 19 (114 terms)
- `behavioral` — low precision (0.2738); high df (168) — in: leaf 7 (300 terms)
- `in vivo` — low precision (0.2848); high df (165) — in: leaf 3 (641 terms)
- `best` — low precision (0.2532); high df (158) — in: leaf 13 (189 terms)
- `academic` — low precision (0.2532); high df (154) — in: leaf 14 (172 terms)
- `therapeutic` — low precision (0.2697); high df (152) — in: leaf 3 (641 terms)
- `economic` — low precision (0.2533) — in: leaf 13 (189 terms)
- `interventions` — low precision (0.2819) — in: leaf 7 (300 terms)
- `members` — low precision (0.2517) — in: leaf 14 (172 terms)
- `evidence` — low precision (0.2553) — in: leaf 7 (300 terms)
- `conference` — low precision (0.1929) — in: leaf 12 (93 terms)
- `surface` — low precision (0.2878) — in: leaf 16 (132 terms)
- `in vitro` — low precision (0.2464) — in: leaf 3 (641 terms)
- `policy` — low precision (0.2713) — in: leaf 13 (189 terms)
- `scalable` — low precision (0.3023) — in: leaf 20 (284 terms)
- `differences` — low precision (0.216) — in: leaf 7 (300 terms)
- `signaling` — low precision (0.2114) — in: leaf 3 (641 terms)
- `professional` — low precision (0.2545) — in: leaf 14 (172 terms)
- `optical` — low precision (0.3178) — in: leaf 16 (132 terms)
- `college` — low precision (0.2857) — in: leaf 14 (172 terms)
- `age` — low precision (0.24) — in: leaf 7 (300 terms)
- `expression` — low precision (0.2784) — in: leaf 3 (641 terms)
- `binding` — low precision (0.3125) — in: leaf 3 (641 terms)
- `deployment` — low precision (0.2021) — in: leaf 21 (211 terms)
- `organizations` — low precision (0.2418) — in: leaf 13 (189 terms)
- `adults` — low precision (0.3444) — in: leaf 7 (300 terms)
- `secure` — low precision (0.2667) — in: leaf 20 (284 terms)
- `stakeholders` — low precision (0.2874) — in: leaf 13 (189 terms)
- `code` — low precision (0.3452) — in: leaf 20 (284 terms)
- `climate` — low precision (0.3377) — in: leaf 11 (129 terms)
- `partnership` — low precision (0.25) — in: leaf 14 (172 terms)
- `operating` — low precision (0.2329) — in: leaf 21 (211 terms)
- `urban` — low precision (0.2877) — in: leaf 13 (189 terms)
- `open-source` — low precision (0.3056) — in: leaf 20 (284 terms)
- `uncertainty` — low precision (0.3194) — in: leaf 19 (114 terms)
- `inference` — low precision (0.2985) — in: leaf 19 (114 terms)
- `travel` — low precision (0.3433) — in: leaf 12 (93 terms)
- `attacks` — low precision (0.3125) — in: leaf 20 (284 terms)
- `leadership` — low precision (0.2881) — in: leaf 14 (172 terms)
- `professional development` — low precision (0.2778) — in: leaf 14 (172 terms)
- `recruitment` — low precision (0.2308) — in: leaf 14 (172 terms)
- `inhibition` — low precision (0.22) — in: leaf 3 (641 terms)
- `mental` — low precision (0.2667) — in: leaf 7 (300 terms)
- `acid` — low precision (0.2955) — in: leaf 3 (641 terms)
- `mentor` — low precision (0.2821) — in: leaf 14 (172 terms)
- `social science` — low precision (0.2353) — in: leaf 13 (189 terms)
- `power consumption` — low precision (0.3438) — in: leaf 21 (211 terms)
- `bayesian` — low precision (0.3214) — in: leaf 19 (114 terms)
- `sensor networks` — low precision (0.2963) — in: leaf 21 (211 terms)
- `probabilistic` — low precision (0.2308) — in: leaf 19 (114 terms)
- `open-source software` — low precision (0.2609) — in: leaf 20 (284 terms)
- `venue` — low precision (0.2941) — in: leaf 12 (93 terms)
- `computer systems` — low precision (0.25) — in: leaf 20 (284 terms)
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
- `education` — low precision (0.2297); high df (518) — in: (not in any accepted-length leaf)
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
- `public` — low precision (0.2794); high df (451) — in: (not in any accepted-length leaf)
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
- `environment` — low precision (0.2219); high df (347) — in: leaf 10 (6 terms)
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
- `investigate` — low precision (0.2351); high df (319) — in: (not in any accepted-length leaf)
- `outcomes` — low precision (0.2571); high df (315) — in: (not in any accepted-length leaf)
- `recent` — low precision (0.2166); high df (314) — in: (not in any accepted-length leaf)
- `because` — low precision (0.2492); high df (313) — in: (not in any accepted-length leaf)
- `experiments` — low precision (0.2276); high df (312) — in: (not in any accepted-length leaf)
- `behavior` — low precision (0.2508); high df (311) — in: (not in any accepted-length leaf)
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
- `graduate students` — low precision (0.2241); high df (290) — in: (not in any accepted-length leaf)
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
- `often` — low precision (0.25); high df (276) — in: (not in any accepted-length leaf)
- `collaboration` — low precision (0.2255); high df (275) — in: (not in any accepted-length leaf)
- `limited` — low precision (0.2945); high df (275) — in: (not in any accepted-length leaf)
- `includes` — low precision (0.3004); high df (273) — in: (not in any accepted-length leaf)
- `dynamics` — low precision (0.2296); high df (270) — in: (not in any accepted-length leaf)
- `efforts` — low precision (0.2714); high df (269) — in: (not in any accepted-length leaf)
- `years` — low precision (0.1866); high df (268) — in: (not in any accepted-length leaf)
- `energy` — low precision (0.3034); high df (267) — in: (not in any accepted-length leaf)
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
- `innovative` — low precision (0.2812); high df (256) — in: (not in any accepted-length leaf)
- `then` — low precision (0.3083); high df (253) — in: (not in any accepted-length leaf)
- `natural` — low precision (0.2738); high df (252) — in: (not in any accepted-length leaf)
- `so` — low precision (0.2738); high df (252) — in: (not in any accepted-length leaf)
- `some` — low precision (0.2072); high df (251) — in: (not in any accepted-length leaf)
- `individual` — low precision (0.2651); high df (249) — in: (not in any accepted-length leaf)
- `technical` — low precision (0.2731); high df (249) — in: (not in any accepted-length leaf)
- `underrepresented` — low precision (0.2169); high df (249) — in: (not in any accepted-length leaf)
- `functional` — low precision (0.254); high df (248) — in: (not in any accepted-length leaf)
- `primary` — low precision (0.2419); high df (248) — in: (not in any accepted-length leaf)
- `processing` — low precision (0.2632); high df (247) — in: (not in any accepted-length leaf)
- `components` — low precision (0.2787); high df (244) — in: (not in any accepted-length leaf)
- `infrastructure` — low precision (0.2992); high df (244) — in: (not in any accepted-length leaf)
- `achieve` — low precision (0.2881); high df (243) — in: (not in any accepted-length leaf)
- `nature` — low precision (0.2263); high df (243) — in: (not in any accepted-length leaf)
- `access` — low precision (0.314); high df (242) — in: (not in any accepted-length leaf)
- `wide` — low precision (0.2282); high df (241) — in: (not in any accepted-length leaf)
- `local` — low precision (0.2218); high df (239) — in: (not in any accepted-length leaf)
- `participation` — low precision (0.2552); high df (239) — in: (not in any accepted-length leaf)
- `expected` — low precision (0.2542); high df (236) — in: (not in any accepted-length leaf)
- `evaluate` — low precision (0.2766); high df (235) — in: (not in any accepted-length leaf)
- `i` — low precision (0.2766); high df (235) — in: (not in any accepted-length leaf)
- `platform` — high df (235) — in: (not in any accepted-length leaf)
- `even` — low precision (0.2692); high df (234) — in: (not in any accepted-length leaf)
- `facilitate` — low precision (0.2436); high df (234) — in: (not in any accepted-length leaf)
- `industry` — low precision (0.2876); high df (233) — in: (not in any accepted-length leaf)
- `quality` — low precision (0.2629); high df (232) — in: (not in any accepted-length leaf)
- `biology` — high df (230) — in: (not in any accepted-length leaf)
- `core` — low precision (0.2739); high df (230) — in: (not in any accepted-length leaf)
- `currently` — low precision (0.2402); high df (229) — in: (not in any accepted-length leaf)
- `chemical` — high df (227) — in: (not in any accepted-length leaf)
- `questions` — low precision (0.2687); high df (227) — in: (not in any accepted-length leaf)
- `student` — low precision (0.1911); high df (225) — in: (not in any accepted-length leaf)
- `interest` — low precision (0.287); high df (223) — in: (not in any accepted-length leaf)
- `stem` — low precision (0.278); high df (223) — in: (not in any accepted-length leaf)
- `variety` — low precision (0.287); high df (223) — in: (not in any accepted-length leaf)
- `out` — low precision (0.2036); high df (221) — in: (not in any accepted-length leaf)
- `what` — low precision (0.2579); high df (221) — in: (not in any accepted-length leaf)
- `would` — low precision (0.25); high df (220) — in: (not in any accepted-length leaf)
- `people` — low precision (0.3379); high df (219) — in: (not in any accepted-length leaf)
- `structural` — low precision (0.2511); high df (219) — in: (not in any accepted-length leaf)
- `treatment` — low precision (0.2831); high df (219) — in: (not in any accepted-length leaf)
- `management` — low precision (0.2627); high df (217) — in: (not in any accepted-length leaf)
- `computing` — low precision (0.2546); high df (216) — in: (not in any accepted-length leaf)
- `no` — low precision (0.2419); high df (215) — in: (not in any accepted-length leaf)
- `leading` — low precision (0.2477); high df (214) — in: (not in any accepted-length leaf)
- `possible` — low precision (0.3084); high df (214) — in: (not in any accepted-length leaf)
- `scale` — low precision (0.2477); high df (214) — in: (not in any accepted-length leaf)
- `yet` — low precision (0.2664); high df (214) — in: (not in any accepted-length leaf)
- `features` — low precision (0.2488); high df (213) — in: (not in any accepted-length leaf)
- `clinical` — low precision (0.2972); high df (212) — in: (not in any accepted-length leaf)
- `expertise` — high df (211) — in: (not in any accepted-length leaf)
- `next` — low precision (0.2227); high df (211) — in: (not in any accepted-length leaf)

... and 1026 more, all in smaller/less-consequential leaves (see outputs/kw_vocab_candidates.json for the full list).

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