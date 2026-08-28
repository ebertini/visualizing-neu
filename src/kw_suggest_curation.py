"""
kw_suggest_curation.py — Phase 4a assisted review: writes
outputs/keyword_topics.suggested.json, a first-pass curation of
outputs/keyword_topics.draft.json with proposed labels and accept/reject/
review calls for every parent and leaf, so the human curator reviews/adjusts
suggestions rather than starting from a blank 25-leaf list.

The judgment calls below (SUGGESTED_PARENTS / SUGGESTED_LEAVES) were made by
reading every leaf's and parent's actual term list in
outputs/keyword_topics.draft.json (as of the run described in each entry's
`notes`) — this is genuine content review, not a mechanical heuristic, which
is why it's baked in as data rather than derived from term statistics. If the
draft is regenerated with different cluster ids (a re-run of
kw_vocab_discover.py/kw_term_cluster.py), this script's suggestions will not
line up — regenerate the review by hand-inspecting the new draft againrather
than trusting stale ids silently. `_check_ids_match` guards against exactly
that: it fails loudly if the draft's leaf/parent ids don't match what this
script expects.

Status values used: "suggest_accept", "suggest_reject", "suggest_review"
(genuinely ambiguous, needs a human call either way). NEVER writes to
outputs/topic_keywords.json — this is a separate, clearly-provenanced
suggestion file the curator diffs against or copies from at their discretion.

Run:
    python3 -m src.kw_suggest_curation
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUTS = REPO_ROOT / "outputs"
DRAFT_PATH = OUTPUTS / "keyword_topics.draft.json"
SUGGESTED_PATH = OUTPUTS / "keyword_topics.suggested.json"

# Reviewed against the draft generated after: boundary-fragment filter +
# bare-possessive-"s" filter + c-TF-IDF-vs-canonical-partition selection +
# centered doc-centroid clustering (k_parent=9, k_leaf=25).
SUGGESTED_PARENTS = {
    "P1": ("Biomedical Sciences", "suggest_accept",
           "Molecular/cellular biology (leaf 3) + neuroscience (leaf 2) form a "
           "coherent biomedical parent. Leaf 1 is degenerate noise — reject it, "
           "not the parent."),
    "P2": ("Public & Behavioral Health", "suggest_accept",
           "Dominated by leaf 7 (300 terms, clean). 5 of its 6 leaves are "
           "degenerate 1-3 term noise clusters — reject those, keep the parent "
           "for leaf 7."),
    "P3": ("Coastal & Environmental Ecology", "suggest_accept",
           "Leaf 11 is clean and large; leaf 10 is a small incoherent grab-bag "
           "(fire/flame mixed with cross-disciplinary/multidisciplinary) — "
           "reject leaf 10, not the parent."),
    "P4": ("Workforce Development, Policy & Broadening Participation",
           "suggest_accept",
           "All 3 leaves (conference travel, social science/policy, faculty "
           "diversity/mentoring) are real, distinct, and coherent — a genuine "
           "'human capital' parent theme."),
    "P5": ("Materials Science & Structural/Civil Engineering", "suggest_review",
           "Both leaves (materials/nanotech, earthquake/civil engineering) are "
           "individually clean and acceptable, but the PARENT pairing is "
           "heterogeneous — they're only embedding-adjacent because both "
           "involve physical structures/materials under stress. Consider "
           "whether this should stay one parent or whether a future curation "
           "round should relabel/split it once more parents are available."),
    "P6": ("Algebra, Geometry & Mathematical Physics", "suggest_accept",
           "Single clean leaf, no changes needed."),
    "P7": (None, "suggest_reject",
           "Only leaf is 2 terms ('higher', 'ap') — no coherent theme, reject "
           "the whole parent."),
    "P8": ("Computing Systems, Networking & Cybersecurity", "suggest_accept",
           "3 of 5 leaves are clean, coherent, and substantial (control/CPS/ML, "
           "software/security, wireless networking, detection/sensing — note "
           "detection is actually a 4th accepted leaf). 2 leaves (alternative/cas; "
           "and none others) are degenerate — reject those only."),
    "P9": (None, "suggest_reject",
           "Both leaves are 1-2 term noise ('disruption'/'timing'; 'tracing') "
           "— reject the whole parent."),
}

SUGGESTED_LEAVES = {
    "1": (None, "suggest_reject", "3 terms ('should','radical','precisely') — no theme."),
    "2": ("Neuroscience & Neural Circuits", "suggest_accept",
          "Genuinely coherent: neurons, neural circuits, synaptic, optogenetic, "
          "c. elegans (model organism) all fit. 'image'/'reconstruction'/'mr' "
          "read as neuroimaging-adjacent, consistent with the theme."),
    "3": ("Molecular & Cellular Biomedicine", "suggest_accept",
          "641 terms, dominant biomedical cluster — clean, no boundary-fragment "
          "pollution remaining."),
    "4": (None, "suggest_reject", "2 terms ('interpretation','mine') — no theme."),
    "5": (None, "suggest_reject", "1 term ('become') — tokenization noise, not content."),
    "6": (None, "suggest_reject", "3 terms ('growing','favor','yielding') — no theme."),
    "7": ("Public & Behavioral Health", "suggest_accept",
          "300 terms, matches the original canonical BERTopic label for this "
          "theme almost exactly — high confidence."),
    "8": (None, "suggest_reject", "3 terms ('proximity','minutes','matching') — no theme."),
    "9": (None, "suggest_reject",
          "1 term ('ve') — a tokenization artifact from a contraction (we've/"
          "they've), not content. Same family as the possessive-'s' bug fixed "
          "in kw_harvest.py, too small-impact (1 term) to warrant another "
          "systematic filter pass."),
    "10": (None, "suggest_review",
           "6 terms, incoherent mix (fire/flame vs. cross-disciplinary/"
           "multidisciplinary vs. 'pd' — ambiguous acronym). Likely reject, "
           "but small enough a human should eyeball the actual grants before "
           "dropping in case 'fire' hazard research is a real, if thin, theme here."),
    "11": ("Coastal & Environmental Ecology", "suggest_accept",
           "129 terms, clean coastal/ecological/climate vocabulary."),
    "12": ("Conference & Student Travel Awards", "suggest_accept",
           "93 terms, the NSF conference/travel-funding-instrument theme found "
           "independently by both Plan A and Plan B during discovery — a real, "
           "distinct funding-mechanism cluster, not noise."),
    "13": ("Social Science & Public Policy", "suggest_accept",
           "189 terms. Some generic words ('build','best','issues') dilute "
           "precision but the core policy/stakeholder/social-science vocabulary "
           "is real and coherent."),
    "14": ("Faculty Development, Diversity & Institutional Partnerships",
           "suggest_accept",
           "172 terms, clean broadening-participation/mentoring vocabulary. One "
           "stray term, 'environmental health', looks like an outlier from a "
           "specific grant's title rather than this leaf's real theme — "
           "consider rejecting just that one term during your pass."),
    "15": ("Civil & Earthquake Engineering", "suggest_accept",
           "46 terms, very clean (NEES/NEESR are legitimate NSF earthquake-"
           "engineering program acronyms, not noise)."),
    "16": ("Materials Science & Nanotechnology", "suggest_accept",
           "132 terms, clean materials/nanotech vocabulary; 'high school'/"
           "'outreach' reflect broader-impacts language in these grants, "
           "consistent with the theme rather than noise."),
    "17": ("Algebra, Geometry & Mathematical Physics", "suggest_accept",
           "125 terms, very clean pure-math + math-physics vocabulary."),
    "18": (None, "suggest_reject", "2 terms ('higher','ap') — no theme."),
    "19": ("Control Systems, Cyber-Physical Systems & Machine Learning",
           "suggest_accept",
           "114 terms, coherent CPS/control-theory/ML vocabulary."),
    "20": ("Software Systems & Cybersecurity", "suggest_accept",
           "284 terms, coherent. A few residual grant-boilerplate phrases "
           "survived the mechanical filters because they don't start/end with "
           "a function word ('project develops', 'significance and importance', "
           "'twc' — an NSF Trustworthy Computing program acronym) — reject "
           "these individually during your pass; they're exactly the class of "
           "thing the mechanical filter can't catch."),
    "21": ("Wireless Networking & Embedded Systems", "suggest_accept",
           "211 terms, clean wireless/networking/embedded-systems vocabulary."),
    "22": (None, "suggest_reject", "2 terms ('alternative','cas') — no theme."),
    "23": ("Detection & Sensing Systems", "suggest_accept",
           "20 terms, coherent detection/sensing/identification vocabulary."),
    "24": (None, "suggest_reject", "2 terms ('disruption','timing') — no theme."),
    "25": (None, "suggest_reject", "1 term ('tracing') — no theme."),
}


def _check_ids_match(draft: dict) -> None:
    draft_leaves = set(draft["leaves"].keys())
    draft_parents = set(draft["parents"].keys())
    suggested_leaves = set(SUGGESTED_LEAVES.keys())
    suggested_parents = set(SUGGESTED_PARENTS.keys())
    if draft_leaves != suggested_leaves or draft_parents != suggested_parents:
        raise ValueError(
            "Draft's leaf/parent ids don't match this script's hardcoded "
            "suggestions — the draft was regenerated since this review was "
            "written. Re-review the new draft's actual term lists by hand "
            "before updating SUGGESTED_LEAVES/SUGGESTED_PARENTS; do not assume "
            "stale ids still refer to the same clusters.\n"
            f"  draft leaves not in suggestions: {draft_leaves - suggested_leaves}\n"
            f"  suggestion leaves not in draft: {suggested_leaves - draft_leaves}\n"
            f"  draft parents not in suggestions: {draft_parents - suggested_parents}\n"
            f"  suggestion parents not in draft: {suggested_parents - draft_parents}"
        )


def build_suggested(draft: dict) -> dict:
    _check_ids_match(draft)
    out = json.loads(json.dumps(draft))  # deep copy
    out["_meta"]["provenance"] = "suggested"
    out["_meta"]["curation"] = {
        "status": "suggested", "curated_by": "assistant (unconfirmed — human must review)",
        "curated_at": "",
    }
    for pid, (label, status, notes) in SUGGESTED_PARENTS.items():
        p = out["parents"][pid]
        if label:
            p["label"] = label
        p["status"] = status
        p["notes"] = notes
    for lid, (label, status, notes) in SUGGESTED_LEAVES.items():
        leaf = out["leaves"][lid]
        if label:
            leaf["label"] = label
        leaf["status"] = status
        leaf["notes"] = notes
    return out


def main() -> None:
    draft = json.loads(DRAFT_PATH.read_text())
    suggested = build_suggested(draft)
    SUGGESTED_PATH.write_text(json.dumps(suggested, indent=2))
    n_accept_leaf = sum(1 for _, s, _ in SUGGESTED_LEAVES.values() if s == "suggest_accept")
    n_reject_leaf = sum(1 for _, s, _ in SUGGESTED_LEAVES.values() if s == "suggest_reject")
    n_review_leaf = sum(1 for _, s, _ in SUGGESTED_LEAVES.values() if s == "suggest_review")
    print(f"wrote {SUGGESTED_PATH}")
    print(f"  leaves: {n_accept_leaf} suggest_accept, {n_reject_leaf} suggest_reject, "
          f"{n_review_leaf} suggest_review (of {len(SUGGESTED_LEAVES)} total)")
    n_accept_p = sum(1 for _, s, _ in SUGGESTED_PARENTS.values() if s == "suggest_accept")
    n_reject_p = sum(1 for _, s, _ in SUGGESTED_PARENTS.values() if s == "suggest_reject")
    n_review_p = sum(1 for _, s, _ in SUGGESTED_PARENTS.values() if s == "suggest_review")
    print(f"  parents: {n_accept_p} suggest_accept, {n_reject_p} suggest_reject, "
          f"{n_review_p} suggest_review (of {len(SUGGESTED_PARENTS)} total)")


if __name__ == "__main__":
    main()
