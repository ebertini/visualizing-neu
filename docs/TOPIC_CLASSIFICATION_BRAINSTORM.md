# Keyword-classifier brainstorm — outcome & next design questions

Record of two conversations with Enrico on the keyword→classifier topic method, and what's still open going into the next design pass. No longer pre-meeting prep — the meeting happened; this is what came out of it plus the narrowed set of questions that remain.

## RESOLVED (2026-08-29) — supersedes the "hybrid: curation + LLM" framing below

**Both of the two mechanisms this doc's "Where things landed" section left open
are now resolved in actually-built, actually-running code — not by the path
this doc originally recorded.** This has **not yet been communicated back to
Enrico** — say so plainly if this doc, or its resolution, comes up with him.

1. **Keyword-list extraction/curation** did NOT end up being a light
   proofreading pass on BERTopic's existing 25-topic c-TF-IDF lists (the
   "second exchange" resolution below). It became a full, independent
   discovery-and-curation pipeline (Plan A vs. Plan B, compared head-to-head;
   Plan B — cluster candidate keywords directly, not documents first — won on
   every measured axis) followed by a genuine leaf-by-leaf human curation
   pass (recursive sub-clustering + real-document polysemy checks for
   ambiguous terms, catching two real content-population bugs and several
   genuinely polysemous terms a label-only review would have missed). Result:
   **31 leaves / 7 parents**, 831 curated keyword terms, 661 documented
   rejections, held in `outputs/topic_keywords.json` (`src/kw_curation.py
   --check` passing 0 errors). This directly answers most of the "Open
   questions — curation" section below (still genuinely open: "which
   student/prior work" — unnamed).
2. **The topic-to-document link is a deterministic BM25F scorer**
   (`src/classify_by_keywords.py`), **not an LLM** as the "second exchange"
   below concluded. Chosen specifically for the properties an LLM can't
   offer: fully offline, zero marginal cost per re-run, exactly reproducible,
   and every assignment's evidence is inspectable (which curated terms
   fired, in which field, at what weight — see `matched_detail_json` in
   `data/processed/topic_keyword_assignments.parquet`). This resolves nearly
   every question in "Open questions — the LLM classification step" below by
   making them moot (no LLM = no prompt design, no per-call cost, no
   reproducibility concern) rather than by answering them as asked.
   The **abstain rule** question (can the classifier say "none of these fit")
   is answered concretely: `conf_tier == "none"` with a named
   `unassigned_reason` (`no_usable_text`, `placeholder_title_only`, or
   `no_keyword_evidence`) — down to **100 grants / $53.7M / 2.5% of dollars**,
   from BERTopic's 697 / $583M / 26.7%.
   An LLM is **not deleted from the design** — it's demoted to an optional,
   off-by-default Phase 4c layer (`src/adjudicate_low_confidence.py`, not yet
   run — no `ANTHROPIC_API_KEY` in this environment), scoped ONLY to the
   `conf_tier ∈ {low, none}` tail (a few hundred docs, not the corpus), given
   the BM25F scorer's own top-5 candidate leaves rather than "all 31" or "the
   raw text with no structure" — closer to the *"a very constrained
   candidate list"* framing than "the LLM freelances a topic," genuinely
   addressing the multi-label/prompt-design/single-call-vs-many questions
   below, just not as the primary mechanism.

**The "How we'll know it worked" section's plan is also now substantially
executed, not just proposed**: a stratified gold set exists
(`data/gold/topic_gold_set.csv`, n=180, built by `src/build_gold_sample.py`)
but has **not been human-labeled yet** — real accuracy/calibration numbers
don't exist. What DOES exist: parent-level agreement with BERTopic (67.9%,
borderline per the redo plan's own stated bands) and a title-only-
normalization check that currently **fails** (the `W_TITLE` BM25F constant
over-boosts short docs — a real, uncalibrated limitation, not swept under
the rug) — see `notebooks/09_keyword_classifier_validation.ipynb`.

(UI feedback from the same conversation — removing PI-matched/abstract facets, a new parent-theme palette, a "none" color option, label abbreviation, grant title on hover — has been implemented separately in `what_we_can_see.html` and isn't covered here.)

---

## Where things landed

**First exchange (Slack).** Confirmed the architecture — a transparent classifier where topics are defined by human-inspectable keyword lists, and documents are linked to topics through those lists — while leaving two mechanisms explicitly open: how the keyword list gets extracted/curated, and what function links topics to documents through them.

**Second exchange (in person).** Talking through the existing pipeline — SPECTER2 embeddings, BERTopic, clusters already computed — resolved the first mechanism largely by recognizing it already exists: "cluster documents, then extract keywords from the clusters" is exactly what the BERTopic pipeline already does. The 25 existing topics and their c-TF-IDF keyword sets (`docs/EnricoVis/data/topics.json`) are a legitimate Step-1 output as-is — no new clustering work is required. (What a curation pass on those lists still needs to cover is its own open question below — this doesn't mean the lists are ready to use unmodified.)

On the second mechanism — how a document actually gets connected to a topic — the resolution is a **hybrid**, not a single method:

1. A **manual curation pass** on the existing topic labels/keyword lists — a human review step.
2. An **LLM**, given a grant's text and the curated keyword lists, decides which topic(s) it belongs to — replacing both the hand-coded scoring-function idea (count / TF-IDF-weighted / coverage matching) and a trained classifier (logistic regression / random forest / XGBoost) that were both on the table before.

This is a real decision, not just a restatement of the Slack message — it resolves the *shape* of the method. It is not a finished spec: LLM choice, prompt design, cost at 2,676-grant scale, and exactly how curation and classification sequence together are all still undecided. **Building the actual pipeline is separate, future work — not started, and not scoped yet.**

"Which student, which prior work" (the person Enrico wants looped in) — no update; still unresolved as far as this record shows.

## What we can see notes - open questions 2026-08-21

* add a very faint grid line for every grant and every pi tab
* remove the default grey line that goes in empty cells for every grant and every pi tab
* add dollars earned from grants PI's earned at northeastern University
* clicking anywhere outside of the option dial should close it
* filter/remove out certain attributes from the grid display available right now (stretch)
* academic rank is an interesting example of nested labels - all the teaching professors should be grouped together, associate professors together, and full professors together - which is working correctly in the current grid display but not for coloring (stretch)
* move the page hosting to its own unique github pages - Enrico will invite me to a project to set this up. 
* Send Paolo an email - to meet sometime next week - check if he is in Boston and then schedule a meeting accordingly.

* Add PI information in grant tooltip for every grant tab - and grant number is inconsequential to audience
* Add dollar band to the column/row overview info for quicker reference. 
* What is the label that states the dollar total for cells (grant buckets)
* Have entry point questions that set up the options in a certain pattern to answer those questions - potential drivers - have a need suggestion? tab at the top that gives a list of questions that you can select from that will automatically configure the options to help answer those questions.
* make sort by and color by more intuitive and user-friendly, potentially adding tooltips or explanations for each option - for sort by - size of dollar and size of what - need clarification. 
* For each grant how many different colleges does it involve?

## What we can see notes — addressed 2026-08-17

All six items below are implemented in `docs/TopicVizPrototypes/what_we_can_see.html`
(mark size fixed at 4.8px regardless of Rows/Columns arrangement; the dock is a floating
overlay, default-collapsed; the Selected panel is a floating card, not a modal, opened by
click and closed via its own close button or Esc; "Arrange by"/"Split by" renamed to
Rows/Columns; drawer prose trimmed throughout). *"Selected grants should be a pop up"* is
interpreted as *floating card*, not a blocking modal — a modal was tried in an earlier round
and explicitly rejected (marks are already individually clickable once the click-precision
problem is fixed, which is the actual thing a modal would have added).

* ~~remove a lot of the text...~~ — drawers cut to 1–2 sentences per section.
* ~~preserve the size of the individual grant boxes~~ — one fixed mark size (4.8px) for
  every Rows × Columns combination; only the number of columns per bin adapts to available
  width.
* ~~selected grants should be a pop up~~ — floating card, not a modal (see above).
* ~~"arrange by"/"split by" → rows/columns~~ — done.
* ~~control panels as an overlay~~ — the dock floats over the chart, default-collapsed, no
  longer reserves layout width.
* ~~whats missing & where it goes, split by grants vs. PIs, absorb coverage's bar-graph
  detail~~ — see "open questions" below, now resolved into the shipped design.

## open questions — resolved 2026-08-17

* **Which tables have what missing (grants / PIs / abstracts)** — `missingness.json` now has
  three grains (`grants` n=2,676, `pis` n=2,247 roster faculty, `abstract_records` n=8,075 raw
  upload records), each scored against its own population with a plain-language `where` string
  per field.
* **What's missing, split by grants vs. PIs, folding in coverage's detail** — the "What's
  missing & where it goes" tab now has a Grants/PIs/Abstract records switch over the missing-
  fields bars, a "Why abstract coverage is so uneven" section carrying the by-agency and
  by-year coverage bars (salvaged from the deprecated Coverage tab's heatmap) plus the kept
  NIH-vs-NSF cliff chart and the mosaic panel's one-line finding, and the funnel unchanged.
  The Coverage tab and the "Does it matter? What we can't see" tab (including its "What we
  cannot see" card deck) are both retired — that content now lives in the caveats already
  surfaced on this tab (`neu_status`, `external_collaborators`, `roster_snapshot`, etc. in
  `viz_meta.json`'s `caveats[]`) rather than as a separate non-quantitative card grid.
* **A table showing what's missing and where it goes, split by grants vs. PIs** — a sortable
  table (Field / Known / Missing / % missing / Recoverable / Where the gap comes from) sits
  below the missing-fields bars on the same tab, grain-aware via the same switch.
* **"Every grant" analog for PIs** — a new "Every PI" tab, over all 2,247 roster faculty
  (not just the 570 with a grant in this corpus — "no grants" is a first-class facet bin, the
  same "nobody's silently dropped" invariant `facets.json` already holds for grants). Dollars
  and parent theme are credited PI-only (not full- or fractional-credit), per the funding-
  credit-model caveat.
* **Cross-check `DataSet/AcAn Grants 2026-08-13.xlsx`** — done; full results in
  `docs/data_quality_report.md` §9. Headline: 198 of the 740 text-less grants become
  recoverable (187 NIH, 11 NSF), concentrated in 2020–2025 (161 of the 198), so the new export
  narrows the NIH cliff more than the pre-check estimate suggested — but doesn't close it.
  **Not adopted into the pipeline this round**: it would break several hardcoded corpus-size
  assertions in `build_viz_aggregates.py` and, more fundamentally, desync the recovered text
  from the frozen BERTopic/SPECTER2 output (2,676 docs, can't be re-fit in this environment).
  It's surfaced today only as a "recoverable" segment in the What's-missing view. The "second
  iteration of What we can see with new topic modelling information" this note asks about —
  re-fitting the topic model over the recovered text, and whether that's the moment to also
  pilot the keyword→classifier method below — is real future work, not yet scoped or started.

---

## Constraints worth keeping in mind

Still true regardless of the new direction:

1. **The only keyword lists that currently exist are outputs of the model this method was originally framed as an alternative to.** `docs/EnricoVis/data/topics.json` holds 25 topics × 10 c-TF-IDF terms each (mirrored in `viz_meta.json`), derived from the BERTopic clusters. Now that reusing them is the explicit plan (rather than a fallback), this is less a concern than a starting point — but it does mean the curation pass is editing BERTopic's own output, not building something independent of it.
2. **There is no BERTopic confidence or coherence score to compare against.** BERTopic ran with hard assignments only (`calculate_probabilities=False`), so every committed artifact is one-hot. The often-quoted "27.6% / 28.0%" figures are *unassigned rates*, not confidences.
3. **The embedding stack (SPECTER2/UMAP/HDBSCAN) can't be re-run in this environment** — no HuggingFace network access locally or in CI. BERTopic can't be refit with a different vectorizer, so the BERTopic side of any comparison is limited to what's already frozen: `{grant → dominant topic, is-noise flag, its 10 top terms, UMAP x/y}`. Note this constraint's original framing — "a purely lexical method would be the only part that reproduces exactly anywhere" — matters less now that assignment goes through an LLM rather than a deterministic keyword-match function; LLM output isn't perfectly reproducible either (see Axis 2 below).
4. **The existing stopword list was tuned against the opposite objective.** `src/clean_text.py`'s `DOMAIN_STOPS` (~124 terms) removes words like *science, engineering, technology, design, data, information, systems, model, method, field* — because they were merging otherwise-distinct *unsupervised* topics. In the BERTopic pipeline these go straight into the vectorizer's stopword list, so multi-word terms containing them — "data science," "systems engineering," "information theory" — never survive into the 10-term lists in the first place. This is now directly the curation pass's problem to fix, not a hypothetical one.
5. **740 of 2,676 grants are title-only** (roughly 10 words vs. ~200 for an abstract). Less mechanically relevant now that matching isn't a hand-coded count function, but still worth keeping in mind for prompt design — a title-only grant gives an LLM much less to work with.
6. **The aggressive text-cleaning path strips digits and hyphens.** `COVID-19`, `CRISPR-based`, `PM2.5`, `2D materials` would silently degrade if a keyword list is built against that cleaned text — worth checking which cleaning path (if any) the curation pass and the LLM prompt actually use.

---

## Open questions — curation (the manual pass on keyword lists)

- **Who does it, and against what criteria?** Still no written procedure — no sampling rule, no accept/reject/merge criteria, no record of *why* a term was added or dropped. If curation is now explicitly part of the method (not just tidying), its reasoning is part of the method's transparency claim, not overhead around it.
- **Does it restore the `DOMAIN_STOPS`-stripped phrases (constraint 4), or is that out of scope?**
- **Is 10 terms per topic enough?** That number was tuned for "enough to label a cluster for a human reading a legend" — a very different bar than "enough for an LLM to reliably tell topics apart," especially for topics that are close to each other in subject matter. Curation may need to *add* terms, not just clean the existing ones.
- **Can a term belong to more than one topic's list, or does curation need to actively disambiguate?** This is close to the center of the whole exercise — the concrete failure this method exists to fix is a term like "neural networks" meaning ML in one context and neuroscience in another (the Alshawabkeh Puerto Rico grants being mis-bucketed under Biomedical was the original motivating example). Curation is exactly where that gets resolved or doesn't.
- **Does the curated output stay a flat term list, or become something richer?** Since the consumer is now an LLM rather than an exact-match function, curation could productively add more than keywords — short topic descriptions, example grants, explicit non-examples — that a keyword-matcher couldn't have used but an LLM prompt can.
- **Which student, which prior work?** Still the highest-leverage unresolved question — `docs/NedaNotebooks/04_topic_validation.ipynb` (lemmatized preprocessing, a richer stopword scheme, coherence + confidence validation already written) remains the strongest candidate for "prior work" if that's what he meant.

## Open questions — the LLM classification step

- **Which LLM**, and what that implies for cost/access — this repo currently makes no LLM API calls anywhere, so this is new infrastructure, not a reuse of something already wired up.
- **Prompt design:** does one call see all 25 topics' curated lists and pick among them (single classification call per grant), or is each grant checked against each topic separately (25 calls per grant)? Very different cost and consistency profiles.
- **Single-label or multi-label?** An LLM makes multi-label materially easier to actually build than a hand-coded scorer would have been — worth revisiting whether single-topic-per-grant (which every existing artifact and visualization currently assumes) is still the right constraint, or whether it's worth reworking that assumption now that it's cheap to support multiple.
- **The abstain rule.** Can the LLM say "none of the 25 topics fit this grant"? BERTopic's Unassigned bucket (808 grants / $607M / 27.8% of the corpus) is the main honesty claim the dashboard is built around, and shrinking it is presumably a chunk of this method's appeal — so this needs an explicit, deliberate answer, not whatever the LLM happens to default to.
- **Cost and latency at scale.** 2,676 grants, and re-run cost every time the corpus or the curated keyword lists change (which, per the curation questions above, may happen more than once).
- **Reproducibility.** LLM output isn't as deterministic as a keyword-match function — worth deciding whether fixing temperature/prompt version is enough for a dashboard meant to be auditable, or whether something else (e.g. majority vote across repeated calls) is needed.
- The old scoring-function question (binary / count / TF-IDF-weighted / coverage matching) and the exact/stemmed/soft-match question are both **moot now** — an LLM doesn't need a hand-coded matching rule. Removed from this list.

## How we'll know it worked

Unchanged from before — still applies directly to an LLM-based classifier's output:

- **There's no ground truth in this project at all** — no grant has ever been hand-labeled by a person. A stratified gold set (maybe 150–200 grants, stratified across agency, abstract-present vs. title-only, and BERTopic-assigned vs. unassigned) would let the LLM classifier be *scored* against something real, not just compared to BERTopic. This doesn't depend on any of the open questions above being resolved first, so it's a reasonable thing to start on independently.
- **What's the actual comparison axis** — raw agreement with BERTopic's hard labels, or specifically how much of the 808-grant Unassigned bucket the new method can confidently place?
- **A validation harness already exists and is a strong fit.** `docs/NedaNotebooks/04_topic_validation.ipynb` already has coherence scoring, a confidence-margin metric with threshold sweeps, manual spot-checks, and a logistic-regression separability test — an LLM classifier's output could drop straight into that harness as a new label column. Separately, `src/build_viz_aggregates.py`'s validation step could absorb a new per-grant assignment as an additional column and get "every grant accounted for" checking for free.
- **Where does this land in the deliverable?** A side-by-side comparison panel added to the dashboard (the still-open "topic-reliability" panel), or an eventual replacement of BERTopic as canonical? Still open, and still changes how much of the existing visualization work would need to move.
