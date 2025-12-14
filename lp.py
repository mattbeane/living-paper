#!/usr/bin/env python3
"""
living_paper v0.1 - local-first claim↔evidence traceability

Public store:  lp_public.sqlite  (safe metadata, shareable)
Private store: lp_private.sqlite (protected pointers; gitignore)

Commands:
  init
  ingest --claims <claims.jsonl> --evidence <evidence.jsonl> --links <links.csv>
  lint
  export --out <dir>

No external dependencies.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

ISO = "%Y-%m-%dT%H:%M:%SZ"

def now() -> str:
    return datetime.utcnow().strftime(ISO)

def die(msg: str, code: int = 2) -> None:
    print(f"[living_paper] ERROR: {msg}", file=sys.stderr)
    raise SystemExit(code)

def project_root() -> Path:
    # assume script is in living_paper/ inside repo
    return Path(__file__).resolve().parents[1]

def lp_dir() -> Path:
    return project_root() / "analysis" / "living_paper"

def ensure_dirs() -> None:
    (lp_dir() / "exports").mkdir(parents=True, exist_ok=True)

def db_paths() -> Tuple[Path, Path]:
    d = lp_dir()
    return d / "lp_public.sqlite", d / "lp_private.sqlite"

def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8")

def exec_sql(db: sqlite3.Connection, sql: str) -> None:
    db.executescript(sql)
    db.commit()

def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(path))
    db.row_factory = sqlite3.Row
    return db

def init_cmd(args: argparse.Namespace) -> None:
    ensure_dirs()
    pub_path, priv_path = db_paths()

    pub = connect(pub_path)
    priv = connect(priv_path)

    schema_dir = Path(__file__).resolve().parent
    exec_sql(pub, read_text(schema_dir / "lp_public_schema.sql"))
    exec_sql(priv, read_text(schema_dir / "lp_private_schema.sql"))

    # Create a default policy file if absent
    policies_dir = lp_dir() / "policies"
    policies_dir.mkdir(parents=True, exist_ok=True)
    dst = policies_dir / "datasets.yaml"
    src = schema_dir / "datasets.yaml"
    if not dst.exists():
        dst.write_text(read_text(src), encoding="utf-8")

    print(f"[living_paper] initialized:\n  {pub_path}\n  {priv_path}\n  {dst}")

def upsert_paper(db: sqlite3.Connection, paper_id: str, title: Optional[str] = None) -> None:
    db.execute(
        "INSERT OR IGNORE INTO paper(paper_id,title,created_at) VALUES (?,?,?)",
        (paper_id, title, now()),
    )
    db.commit()

def ingest_claims(db: sqlite3.Connection, claims_path: Path) -> int:
    n = 0
    with claims_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            required = ["claim_id","paper_id","claim_type","text"]
            for k in required:
                if k not in obj:
                    die(f"claims.jsonl missing '{k}' in line: {line[:200]}")
            upsert_paper(db, obj["paper_id"])

            # Map claim_type if needed (handle legacy values)
            claim_type = obj["claim_type"]
            type_map = {
                "descriptive": "empirical",
                "mechanism": "theoretical",
                "process": "methodological",
                "measurement": "methodological",
            }
            claim_type = type_map.get(claim_type, claim_type)

            db.execute(
                """
                INSERT INTO claim(claim_id,paper_id,claim_type,text,confidence,status,
                                  verification_status,verification_mode,parent_claim_id,frame_id,
                                  created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(claim_id) DO UPDATE SET
                  paper_id=excluded.paper_id,
                  claim_type=excluded.claim_type,
                  text=excluded.text,
                  confidence=COALESCE(excluded.confidence, claim.confidence),
                  status=COALESCE(excluded.status, claim.status),
                  verification_status=COALESCE(excluded.verification_status, claim.verification_status),
                  verification_mode=COALESCE(excluded.verification_mode, claim.verification_mode),
                  parent_claim_id=COALESCE(excluded.parent_claim_id, claim.parent_claim_id),
                  frame_id=COALESCE(excluded.frame_id, claim.frame_id),
                  updated_at=excluded.updated_at
                """,
                (
                    obj["claim_id"],
                    obj["paper_id"],
                    claim_type,
                    obj["text"],
                    obj.get("confidence", 0.5),
                    obj.get("status","draft"),
                    obj.get("verification_status", "unverified"),
                    obj.get("verification_mode","public_provenance"),
                    obj.get("parent_claim_id"),
                    obj.get("frame_id"),
                    now(),
                    now(),
                ),
            )
            n += 1
    db.commit()
    return n

def ingest_evidence(db: sqlite3.Connection, evidence_path: Path) -> int:
    n = 0
    with evidence_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            required = ["evidence_id","paper_id","evidence_type","summary","sensitivity_tier"]
            for k in required:
                if k not in obj:
                    die(f"evidence.jsonl missing '{k}' in line: {line[:200]}")
            upsert_paper(db, obj["paper_id"])
            meta = obj.get("meta", {})
            if not isinstance(meta, dict):
                die("evidence.meta must be an object/dict")
            db.execute(
                """
                INSERT INTO evidence(evidence_id,paper_id,evidence_type,summary,sensitivity_tier,meta_json,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(evidence_id) DO UPDATE SET
                  paper_id=excluded.paper_id,
                  evidence_type=excluded.evidence_type,
                  summary=excluded.summary,
                  sensitivity_tier=excluded.sensitivity_tier,
                  meta_json=excluded.meta_json,
                  updated_at=excluded.updated_at
                """,
                (
                    obj["evidence_id"],
                    obj["paper_id"],
                    obj["evidence_type"],
                    obj["summary"],
                    obj["sensitivity_tier"],
                    json.dumps(meta, ensure_ascii=False),
                    now(),
                    now(),
                ),
            )
            n += 1
    db.commit()
    return n

def ingest_links(db: sqlite3.Connection, links_path: Path) -> int:
    n = 0
    with links_path.open("r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            for k in ["claim_id","evidence_id","relation"]:
                if not row.get(k):
                    die(f"links.csv missing {k} in row: {row}")
            # Weight is now a text enum: central, supporting, peripheral
            weight = row.get("weight", "supporting")
            if weight not in ("central", "supporting", "peripheral"):
                weight = "supporting"  # default fallback
            db.execute(
                """
                INSERT OR REPLACE INTO claim_evidence_link(claim_id,evidence_id,relation,weight,note,created_at)
                VALUES (?,?,?,?,?,?)
                """,
                (row["claim_id"], row["evidence_id"], row["relation"], weight, row.get("note"), now()),
            )
            n += 1
    db.commit()
    return n

def ingest_cmd(args: argparse.Namespace) -> None:
    pub_path, _ = db_paths()
    db = connect(pub_path)

    claims_p = Path(args.claims).resolve()
    evidence_p = Path(args.evidence).resolve()
    links_p = Path(args.links).resolve()

    if not claims_p.exists(): die(f"claims file not found: {claims_p}")
    if not evidence_p.exists(): die(f"evidence file not found: {evidence_p}")
    if not links_p.exists(): die(f"links file not found: {links_p}")

    nc = ingest_claims(db, claims_p)
    ne = ingest_evidence(db, evidence_p)
    nl = ingest_links(db, links_p)

    print(f"[living_paper] ingested: {nc} claims, {ne} evidence items, {nl} links into {pub_path}")

def lint_cmd(args: argparse.Namespace) -> None:
    pub_path, _ = db_paths()
    db = connect(pub_path)

    # Rule 1: every claim must have >=1 evidence link
    q = db.execute("""
      SELECT c.claim_id, c.text
      FROM claim c
      LEFT JOIN claim_evidence_link l ON l.claim_id = c.claim_id
      GROUP BY c.claim_id
      HAVING COUNT(l.evidence_id) = 0
    """).fetchall()
    if q:
        ids = ", ".join([row["claim_id"] for row in q[:10]])
        die(f"{len(q)} claim(s) have zero linked evidence (e.g., {ids}). Add links or mark claim as out-of-scope.")

    # Rule 2: every link must point to existing claim/evidence
    bad_links = db.execute("""
      SELECT l.claim_id, l.evidence_id, l.relation
      FROM claim_evidence_link l
      LEFT JOIN claim c ON c.claim_id = l.claim_id
      LEFT JOIN evidence e ON e.evidence_id = l.evidence_id
      WHERE c.claim_id IS NULL OR e.evidence_id IS NULL
    """).fetchall()
    if bad_links:
        ex = bad_links[0]
        die(f"Found broken link(s): e.g., claim_id={ex['claim_id']} evidence_id={ex['evidence_id']} relation={ex['relation']}")

    # Rule 3: orphan evidence is allowed but warned (often indicates unused extraction)
    orphan = db.execute("""
      SELECT e.evidence_id
      FROM evidence e
      LEFT JOIN claim_evidence_link l ON l.evidence_id = e.evidence_id
      GROUP BY e.evidence_id
      HAVING COUNT(l.claim_id)=0
    """).fetchall()
    if orphan:
        print(f"[living_paper] WARNING: {len(orphan)} evidence item(s) are not linked to any claim (orphaned).")

    print("[living_paper] lint OK")

def export_cmd(args: argparse.Namespace) -> None:
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    pub_path, _ = db_paths()
    db = connect(pub_path)

    # quote_provenance.csv:
    # evidence items where evidence_type == 'quote' and sensitivity_tier == PUBLIC
    # Flatten common metadata keys if present.
    rows = db.execute("""
      SELECT e.evidence_id, e.meta_json
      FROM evidence e
      WHERE e.evidence_type='quote' AND e.sensitivity_tier='PUBLIC'
      ORDER BY e.evidence_id
    """).fetchall()

    prov_path = out / "qual_metadata"
    prov_path.mkdir(parents=True, exist_ok=True)
    csv_path = prov_path / "quote_provenance.csv"

    # choose a stable set of columns
    cols = ["quote_id","interview_id","informant_role_bin","informant_tenure_bin","site_bin","line_start","line_end","mechanism_hypothesis","evidence_type"]
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            meta = json.loads(r["meta_json"] or "{}")
            w.writerow({
                "quote_id": r["evidence_id"],
                "interview_id": meta.get("interview_id"),
                "informant_role_bin": meta.get("informant_role_bin"),
                "informant_tenure_bin": meta.get("informant_tenure_bin"),
                "site_bin": meta.get("site_bin"),
                "line_start": meta.get("line_start"),
                "line_end": meta.get("line_end"),
                "mechanism_hypothesis": meta.get("mechanism_hypothesis"),
                "evidence_type": meta.get("evidence_type"),
            })

    # evidence_summary.md (by claim)
    proc_path = out / "process"
    proc_path.mkdir(parents=True, exist_ok=True)
    summ_path = proc_path / "evidence_summary.md"

    claims = db.execute("""
      SELECT claim_id, claim_type, text
      FROM claim
      ORDER BY claim_id
    """).fetchall()

    with summ_path.open("w", encoding="utf-8") as f:
        f.write("# Evidence summary (auto-generated)\n\n")
        for c in claims:
            f.write(f"## {c['claim_id']} ({c['claim_type']})\n\n")
            f.write(c["text"].strip() + "\n\n")
            links = db.execute("""
              SELECT l.relation, l.weight, e.evidence_id, e.evidence_type, e.summary
              FROM claim_evidence_link l
              JOIN evidence e ON e.evidence_id = l.evidence_id
              WHERE l.claim_id = ?
              ORDER BY l.relation, e.evidence_id
            """, (c["claim_id"],)).fetchall()
            if not links:
                f.write("_No linked evidence._\n\n")
                continue
            for l in links:
                f.write(f"- **{l['relation']}** ({l['evidence_type']}) `{l['evidence_id']}`: {l['summary']}\n")
            f.write("\n")

    print(f"[living_paper] exported:\n  {csv_path}\n  {summ_path}")

def verify_export_cmd(args: argparse.Namespace) -> None:
    """Export a verification package for external reviewers."""
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    pub_path, _ = db_paths()
    db = connect(pub_path)

    # 1. Claims manifest with verification status
    claims = db.execute("""
      SELECT claim_id, paper_id, claim_type, text, confidence, status,
             verification_status, verified_by, verified_at
      FROM claim
      ORDER BY claim_id
    """).fetchall()

    claims_manifest = out / "claims_manifest.json"
    with claims_manifest.open("w", encoding="utf-8") as f:
        claims_data = []
        for c in claims:
            # Count evidence by relation
            link_counts = db.execute("""
              SELECT relation, COUNT(*) as n
              FROM claim_evidence_link
              WHERE claim_id = ?
              GROUP BY relation
            """, (c["claim_id"],)).fetchall()

            claims_data.append({
                "claim_id": c["claim_id"],
                "paper_id": c["paper_id"],
                "claim_type": c["claim_type"],
                "text": c["text"],
                "confidence": c["confidence"],
                "status": c["status"],
                "verification_status": c["verification_status"],
                "verified_by": c["verified_by"],
                "verified_at": c["verified_at"],
                "evidence_counts": {lc["relation"]: lc["n"] for lc in link_counts},
            })
        json.dump({"claims": claims_data, "generated_at": now()}, f, indent=2)

    # 2. Evidence hashes (for verification without content)
    evidence = db.execute("""
      SELECT evidence_id, paper_id, evidence_type, summary, sensitivity_tier, meta_json
      FROM evidence
      ORDER BY evidence_id
    """).fetchall()

    evidence_manifest = out / "evidence_manifest.json"
    with evidence_manifest.open("w", encoding="utf-8") as f:
        evidence_data = []
        for e in evidence:
            evidence_data.append({
                "evidence_id": e["evidence_id"],
                "paper_id": e["paper_id"],
                "evidence_type": e["evidence_type"],
                "summary": e["summary"] if e["sensitivity_tier"] == "PUBLIC" else "[CONTROLLED]",
                "sensitivity_tier": e["sensitivity_tier"],
                "meta": json.loads(e["meta_json"] or "{}"),
            })
        json.dump({"evidence": evidence_data, "generated_at": now()}, f, indent=2)

    # 3. Link verification checklist
    links = db.execute("""
      SELECT l.claim_id, l.evidence_id, l.relation, l.weight,
             l.verification_status, l.verified_by, l.verified_at, l.note,
             c.text as claim_text, e.summary as evidence_summary
      FROM claim_evidence_link l
      JOIN claim c ON c.claim_id = l.claim_id
      JOIN evidence e ON e.evidence_id = l.evidence_id
      ORDER BY l.claim_id, l.evidence_id
    """).fetchall()

    checklist_path = out / "verification_checklist.md"
    with checklist_path.open("w", encoding="utf-8") as f:
        f.write("# Verification Checklist\n\n")
        f.write(f"Generated: {now()}\n\n")
        f.write("## Instructions\n\n")
        f.write("For each link below, verify that:\n")
        f.write("1. The evidence exists in the source data\n")
        f.write("2. The evidence supports/challenges the claim as indicated\n")
        f.write("3. The summary accurately represents the evidence\n\n")
        f.write("Mark each as: ✓ Verified | ? Uncertain | ✗ Incorrect\n\n")
        f.write("---\n\n")

        current_claim = None
        for l in links:
            if l["claim_id"] != current_claim:
                current_claim = l["claim_id"]
                f.write(f"## {l['claim_id']}\n\n")
                f.write(f"**Claim**: {l['claim_text']}\n\n")

            status_icon = "✓" if l["verification_status"] == "external_verified" else "[ ]"
            f.write(f"- {status_icon} `{l['evidence_id']}` ({l['relation']}, {l['weight']})\n")
            f.write(f"  - Summary: {l['evidence_summary']}\n")
            if l["note"]:
                f.write(f"  - Note: {l['note']}\n")
            if l["verified_by"]:
                f.write(f"  - Verified by: {l['verified_by']} on {l['verified_at']}\n")
            f.write("\n")

    # 4. Summary statistics
    stats_path = out / "verification_stats.json"
    with stats_path.open("w", encoding="utf-8") as f:
        total_claims = len(claims)
        verified_claims = sum(1 for c in claims if c["verification_status"] == "external_verified")
        total_links = len(links)
        verified_links = sum(1 for l in links if l["verification_status"] == "external_verified")

        by_tier = db.execute("""
          SELECT sensitivity_tier, COUNT(*) as n FROM evidence GROUP BY sensitivity_tier
        """).fetchall()

        json.dump({
            "total_claims": total_claims,
            "verified_claims": verified_claims,
            "verification_rate_claims": verified_claims / total_claims if total_claims else 0,
            "total_links": total_links,
            "verified_links": verified_links,
            "verification_rate_links": verified_links / total_links if total_links else 0,
            "evidence_by_tier": {t["sensitivity_tier"]: t["n"] for t in by_tier},
            "generated_at": now(),
        }, f, indent=2)

    print(f"[living_paper] verification package exported to {out}")
    print(f"  - claims_manifest.json ({len(claims)} claims)")
    print(f"  - evidence_manifest.json ({len(evidence)} items)")
    print(f"  - verification_checklist.md ({len(links)} links)")
    print(f"  - verification_stats.json")

def prereview_cmd(args: argparse.Namespace) -> None:
    """Generate pre-review report of contested claims for adjudication."""
    pub_path, _ = db_paths()
    db = connect(pub_path)

    # Find contested claims: those with challenges or low support ratio
    claims = db.execute("""
        SELECT c.claim_id, c.paper_id, c.claim_type, c.text, c.confidence
        FROM claim c
        ORDER BY c.paper_id, c.claim_id
    """).fetchall()

    report = []
    report.append("# Pre-Review Report: Contested Claims\n")
    report.append("Claims requiring adjudication before submission.\n")
    report.append("See PREREVIEW.md for adjudication methodology.\n\n")

    contested_count = 0
    for claim in claims:
        links = db.execute("""
            SELECT l.relation, l.weight, l.note, e.evidence_type
            FROM claim_evidence_link l
            JOIN evidence e ON e.evidence_id = l.evidence_id
            WHERE l.claim_id = ?
        """, (claim['claim_id'],)).fetchall()

        supports = [l for l in links if l['relation'] == 'supports']
        challenges = [l for l in links if l['relation'] == 'challenges']
        qualifies = [l for l in links if l['relation'] == 'qualifies']

        # Flag as contested if: has challenges, or low confidence, or more qualifies than supports
        is_contested = (
            len(challenges) > 0 or
            claim['confidence'] < 0.5 or
            (len(qualifies) > len(supports) and len(supports) < 2)
        )

        if is_contested:
            contested_count += 1
            claim_type_label = "QUANT" if claim['claim_type'] == 'empirical' else "MECHANISM"
            report.append(f"## {claim['claim_id']} [{claim_type_label}]\n")
            report.append(f"**Paper:** {claim['paper_id']}\n")
            report.append(f"**Claim:** {claim['text']}\n")
            report.append(f"**Confidence:** {claim['confidence']}\n\n")

            report.append(f"**Evidence balance:** {len(supports)} supports, {len(challenges)} challenges, {len(qualifies)} qualifies\n\n")

            if challenges:
                report.append("### Challenges to address:\n")
                for c in challenges:
                    report.append(f"- [{c['weight']}] {c['note']}\n")
                report.append("\n")

            if qualifies:
                report.append("### Qualifications:\n")
                for q in qualifies:
                    report.append(f"- [{q['weight']}] {q['note']}\n")
                report.append("\n")

            # Add adjudication prompts based on claim type
            report.append("### Adjudication questions:\n")
            if claim['claim_type'] == 'empirical':
                report.append("- Is challenging evidence qual (perceptions) or quant (data)?\n")
                report.append("- If qual perceptions contradict quant: reclassify as 'illustrates mistaken beliefs'\n")
                report.append("- If competing quant data: investigate data quality/scope\n")
            else:
                report.append("- What does this mechanism predict behaviorally?\n")
                report.append("- Does the quant pattern match or contradict the prediction?\n")
                report.append("- Can competing mechanisms be ruled out by quant?\n")
            report.append("\n---\n\n")

    # Summary
    summary = f"\n## Summary\n\n"
    summary += f"- Total claims: {len(claims)}\n"
    summary += f"- Contested claims: {contested_count}\n"
    summary += f"- Ready for submission: {len(claims) - contested_count}\n"

    report.insert(3, summary)

    out_path = Path(args.out)
    out_path.write_text("".join(report), encoding="utf-8")
    print(f"[living_paper] pre-review report: {contested_count} contested claims written to {out_path}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="lp", description="living_paper v0.1")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="initialize DBs and policies")

    ing = sub.add_parser("ingest", help="ingest claims/evidence/links")
    ing.add_argument("--claims", required=True)
    ing.add_argument("--evidence", required=True)
    ing.add_argument("--links", required=True)

    sub.add_parser("lint", help="run traceability checks")

    ex = sub.add_parser("export", help="export PUBLIC provenance + summaries")
    ex.add_argument("--out", required=True)

    vex = sub.add_parser("verify-export", help="export verification package for external reviewers")
    vex.add_argument("--out", required=True)

    pre = sub.add_parser("prereview", help="generate pre-review report of contested claims")
    pre.add_argument("--out", required=True)

    return p

def main(argv: Optional[Iterable[str]] = None) -> None:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    if args.cmd == "init":
        init_cmd(args)
    elif args.cmd == "ingest":
        ingest_cmd(args)
    elif args.cmd == "lint":
        lint_cmd(args)
    elif args.cmd == "export":
        export_cmd(args)
    elif args.cmd == "verify-export":
        verify_export_cmd(args)
    elif args.cmd == "prereview":
        prereview_cmd(args)
    else:
        die(f"unknown command: {args.cmd}")

if __name__ == "__main__":
    main()
