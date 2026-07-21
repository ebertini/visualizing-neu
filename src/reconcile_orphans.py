"""
reconcile_orphans.py — M2 of docs/TOPIC_WORK_FORWARD_PLAN.md.

Recover the 403 usable orphan abstracts (grant_orphaned_abstracts with
len(abstract) >= 200) back into the NEU corpus using the strict ID crosswalk
built by src/build_dataset.py.

Pipeline order (see plan §4):
    python -m src.build_dataset
    python -m src.reconcile_orphans      # <- this file
    python -m src.build_specter2_embeddings
    python -m src.topics_bertopic

Method
------
1. Attribute each usable orphan to a faculty via personid_to_faculty, filtered
   to resolution_method == 'strict_100pct'. Orphans whose personid does not
   resolve are `unattributed` (audit-only, not touched).
2. For each attributable orphan, score it against the abstract-LESS NEU grants
   that its resolved faculty actually has on record (via faculty_grants):
     - title similarity  : rapidfuzz token_set_ratio(orphan.title, grantname) >= 85
     - date proximity    : |orphan.start_date - grant.startdate| <= 365 days
                           (non-veto if either date is missing)
     - amount overlap    : if orphan.dollar_amount > 0 and grant.totaldollars > 0,
                           |o - n| / max(o, n) <= 0.15 (non-veto if either is 0 —
                           the abstract file's Dollar Amount is unreliable)
3. Bucket each orphan:
     - `update`         : matched an abstract-less NEU grant -> backfill the
                          abstract onto that grant (abstract_source='orphan_recovered')
     - `extra`          : resolved faculty but no grant match -> pseudo-doc in
                          extra_neu_abstracts.parquet (doc_id='orphan-<id>')
     - `unattributed`   : no resolved faculty -> not touched

Outputs
-------
    data/processed/grants.parquet             (enriched; adds `abstract_source`)
    data/processed/extra_neu_abstracts.parquet
    data/processed/grant_orphan_recovery.parquet   (full audit of all 403)
    outputs/orphan_recovery_report.md
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz

# ── Thresholds (plan §5.1; tune after spot-checking grant_orphan_recovery) ──
MIN_ABSTRACT_CHARS = 200
TITLE_MIN = 85          # token_set_ratio
DATE_MAX_DAYS = 365
AMOUNT_TOL = 0.15

REPO_ROOT = Path(__file__).resolve().parent.parent


def _norm(s: str) -> str:
    return str(s or "").strip().lower()


def _date_ok(o_date, n_date) -> bool:
    """Non-veto if either date is missing; else within DATE_MAX_DAYS."""
    if pd.isna(o_date) or pd.isna(n_date):
        return True
    return abs((o_date - n_date).days) <= DATE_MAX_DAYS


def _amount_ok(o_amt, n_amt) -> bool:
    """Non-veto if either amount is missing/zero (abstract $ is unreliable)."""
    try:
        o, n = float(o_amt), float(n_amt)
    except (TypeError, ValueError):
        return True
    if o <= 0 or n <= 0:
        return True
    return abs(o - n) / max(o, n) <= AMOUNT_TOL


def _date_days(o_date, n_date):
    if pd.isna(o_date) or pd.isna(n_date):
        return None
    return abs((o_date - n_date).days)


def reconcile(proc: Path) -> dict:
    grants = pd.read_parquet(proc / "grants.parquet")
    orph = pd.read_parquet(proc / "grant_orphaned_abstracts.parquet")
    p2f = pd.read_parquet(proc / "personid_to_faculty.parquet")
    fg = pd.read_parquet(proc / "faculty_grants.parquet")

    grants["grant_id"] = grants["grant_id"].astype(str)
    grants["abstract"] = grants["abstract"].fillna("").astype(str)
    fg["grant_id"] = fg["grant_id"].astype(str)
    fg["faculty_id"] = fg["faculty_id"].astype(str)

    # Guard: this step is NOT idempotent (backfilled grants would be reclassified
    # as `duplicate` on a second pass). Always run on a fresh grants.parquet.
    if "abstract_source" in grants.columns and (grants["abstract_source"] == "orphan_recovered").any():
        raise SystemExit(
            "grants.parquet already contains orphan_recovered rows — it looks "
            "already reconciled. Re-run `python -m src.build_dataset` first, then "
            "`python -m src.reconcile_orphans`."
        )

    # Initialize abstract_source ('internal' for native abstracts) idempotently.
    if "abstract_source" not in grants.columns:
        grants["abstract_source"] = ""
    grants.loc[(grants["abstract"] != "") & (grants["abstract_source"] == ""),
               "abstract_source"] = "internal"

    # Usable orphans: abstract >= 200 chars.
    orph["abstract"] = orph["abstract"].fillna("").astype(str)
    orph["title"] = orph["title"].fillna("").astype(str)
    orph["personid"] = orph["personid"].astype(str).str.strip()
    usable = orph[orph["abstract"].str.len() >= MIN_ABSTRACT_CHARS].copy()

    # Attribute via strict-100% bridge only.
    strict = p2f[p2f["resolution_method"] == "strict_100pct"][["personid", "faculty_id"]].copy()
    strict["personid"] = strict["personid"].astype(str).str.strip()
    strict["faculty_id"] = strict["faculty_id"].astype(str)
    usable = usable.merge(strict, on="personid", how="left")
    usable["faculty_id"] = usable["faculty_id"].fillna("")

    # Faculty -> ALL their NEU grants (with abstract status). We score against
    # every grant, not just abstract-less ones, so we can tell an `update`
    # (matches an abstract-less grant) from a `duplicate` (matches a grant that
    # ALREADY has an abstract — a re-upload under a new SourceActivityId, which
    # must be dropped not re-added, or we double-count. See ID_RECONCILIATION §5.1).
    pool_cols = grants[["grant_id", "grantname", "startdate", "totaldollars", "abstract"]].copy()
    pool_cols["has_abstract"] = pool_cols["abstract"] != ""
    fac_to_grants = (
        fg.merge(pool_cols.drop(columns=["abstract"]), on="grant_id", how="inner")
          .groupby("faculty_id")
    )
    pool_by_fac = {fid: g for fid, g in fac_to_grants}

    # Score every attributable orphan against ALL of its faculty's grants.
    audit_rows = []
    for _, o in usable.iterrows():
        fid = o["faculty_id"]
        base = {
            "orphan_id": str(o["id"]), "personid": o["personid"], "faculty_id": fid,
            "orphan_title": o["title"][:120],
        }
        if not fid or fid not in pool_by_fac:
            audit_rows.append({**base, "bucket": "unattributed" if not fid else "extra",
                               "matched_grant_id": "", "title_score": None,
                               "date_days": None})
            continue
        cands = pool_by_fac[fid]
        best = None
        for _, g in cands.iterrows():
            ts = fuzz.token_set_ratio(_norm(o["title"]), _norm(g["grantname"]))
            if ts < TITLE_MIN:
                continue
            if not _date_ok(o["start_date"], g["startdate"]):
                continue
            if not _amount_ok(o["dollar_amount"], g["totaldollars"]):
                continue
            dd = _date_days(o["start_date"], g["startdate"])
            key = (ts, -(dd if dd is not None else 10**9))  # high score, then closest date
            if best is None or key > best[0]:
                best = (key, g["grant_id"], ts, dd, bool(g["has_abstract"]))
        if best is None:
            audit_rows.append({**base, "bucket": "extra", "matched_grant_id": "",
                               "title_score": None, "date_days": None})
        else:
            # matched a grant that already has an abstract -> duplicate (drop);
            # matched an abstract-less grant -> update (backfill).
            bucket = "duplicate" if best[4] else "update"
            audit_rows.append({**base, "bucket": bucket, "matched_grant_id": best[1],
                               "title_score": int(best[2]), "date_days": best[3]})

    audit = pd.DataFrame(audit_rows)

    # Resolve grant_id collisions: if two orphans claim the same NEU grant, the
    # higher title_score wins the `update`; the loser is demoted to `extra`.
    upd = audit[audit["bucket"] == "update"].sort_values("title_score", ascending=False)
    winners = upd.drop_duplicates("matched_grant_id", keep="first")
    losers = upd.index.difference(winners.index)
    audit.loc[losers, ["bucket", "matched_grant_id", "title_score", "date_days"]] = \
        ["extra", "", None, None]

    # ── Backfill `update` abstracts onto grants ──────────────────────────────
    o_by_id = usable.set_index(usable["id"].astype(str))
    win = audit[audit["bucket"] == "update"]
    g_idx = grants.set_index("grant_id")
    for _, r in win.iterrows():
        o = o_by_id.loc[r["orphan_id"]]
        gid = r["matched_grant_id"]
        g_idx.loc[gid, "abstract"] = o["abstract"]
        if "title_from_abstract" in g_idx.columns:
            g_idx.loc[gid, "title_from_abstract"] = o["title"]
        g_idx.loc[gid, "abstract_source"] = "orphan_recovered"
    grants = g_idx.reset_index()

    # ── extra_neu_abstracts pseudo-docs ──────────────────────────────────────
    extra_ids = audit[audit["bucket"] == "extra"]["orphan_id"].tolist()
    ex = o_by_id.loc[[i for i in extra_ids if i in o_by_id.index]].copy()
    extra = pd.DataFrame({
        "doc_id": ["orphan-" + str(i) for i in ex["id"]],
        "faculty_id": ex["faculty_id"].values,
        "personid": ex["personid"].values,
        "title": ex["title"].values,
        "abstract": ex["abstract"].values,
        "start_date": ex["start_date"].values,
        "abstract_source": "orphan_extra",
    })

    counts = audit["bucket"].value_counts().to_dict()
    return {"grants": grants, "extra": extra, "audit": audit, "counts": counts,
            "n_usable": len(usable)}


def write_report(res: dict, proc: Path, out: Path) -> str:
    g = res["grants"]
    n_abs = int((g["abstract"] != "").sum())
    src = g["abstract_source"].value_counts().to_dict()
    c = res["counts"]
    n_update = c.get("update", 0)
    n_extra = c.get("extra", 0)
    n_dup = c.get("duplicate", 0)
    n_unattr = c.get("unattributed", 0)
    lines = [
        "# Orphan Recovery Report (M2)",
        "",
        f"Usable orphan abstracts (>= {MIN_ABSTRACT_CHARS} chars): **{res['n_usable']}**",
        "",
        "## Outcome buckets",
        f"- **update** (backfilled onto an abstract-less NEU grant): **{n_update}**",
        f"- **extra** (resolved faculty, no grant match -> pseudo-doc): **{n_extra}**",
        f"- **duplicate** (re-upload of a grant that already has an abstract -> dropped): **{n_dup}**",
        f"- **unattributed** (personid not strict-resolved, dropped): **{n_unattr}**",
        "",
        "## grants.parquet abstract coverage",
        f"- non-empty abstracts now: **{n_abs} / {len(g)}** ({100*n_abs/len(g):.1f}%)",
        f"- by source: " + ", ".join(f"`{k or 'none'}`={v}" for k, v in sorted(src.items())),
        "",
        f"## Corpus for BERTopic (M3) = grants ({len(g)}) + extras ({n_extra}) "
        f"= **{len(g) + n_extra}** documents",
        "",
        f"Thresholds: title token_set_ratio >= {TITLE_MIN}, date +/- {DATE_MAX_DAYS}d, "
        f"amount tol {AMOUNT_TOL:.0%} (non-veto when 0).",
        "",
        "## Spot-check the 10 highest-scoring updates",
        "",
    ]
    top = res["audit"][res["audit"]["bucket"] == "update"].sort_values(
        "title_score", ascending=False).head(10)
    lines += ["| score | date_days | grant_id | orphan_title |", "|---:|---:|---|---|"]
    for _, r in top.iterrows():
        lines.append(f"| {r['title_score']} | {r['date_days']} | {r['matched_grant_id']} | "
                     f"{str(r['orphan_title'])[:70]} |")
    report = "\n".join(lines) + "\n"
    (out / "orphan_recovery_report.md").write_text(report, encoding="utf-8")
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--proc", type=Path, default=REPO_ROOT / "data" / "processed")
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "outputs")
    args = ap.parse_args()
    args.out.mkdir(exist_ok=True)

    res = reconcile(args.proc)
    res["grants"].to_parquet(args.proc / "grants.parquet", index=False)
    res["grants"].to_csv(args.proc / "grants.csv", index=False, encoding="utf-8-sig")
    res["extra"].to_parquet(args.proc / "extra_neu_abstracts.parquet", index=False)
    res["audit"].to_parquet(args.proc / "grant_orphan_recovery.parquet", index=False)
    report = write_report(res, args.proc, args.out)
    print(report)
    print(f"wrote grants.parquet (+abstract_source), extra_neu_abstracts.parquet "
          f"({len(res['extra'])}), grant_orphan_recovery.parquet ({len(res['audit'])})")


if __name__ == "__main__":
    main()
