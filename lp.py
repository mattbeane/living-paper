#!/usr/bin/env python3
"""
living_paper v0.5 - local-first claim↔evidence traceability

Public store:  lp_public.sqlite  (safe metadata, shareable)
Private store: lp_private.sqlite (protected pointers; gitignore)

Commands:
  init
  ingest --claims <claims.jsonl> --evidence <evidence.jsonl> --links <links.csv> [--entities <entities.yaml>]
  lint
  export --out <dir>
  verify-export --out <dir>
  prereview --out <file>
  export-html --paper <paper_id> --out <file>
  export-package --paper <paper_id> --out <folder>

Author tools:
  redact check --input <file.jsonl> --entities <entities.yaml>
  redact apply --input <file.jsonl> --output <file.jsonl> --entities <entities.yaml>

No external dependencies for core. Optional: pyyaml for entity redaction.
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

# Optional redaction support (for authors)
try:
    from redact import EntityRedactor, RedactionStats
    HAS_REDACT = True
except ImportError:
    HAS_REDACT = False
    EntityRedactor = None
    RedactionStats = None

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

def ingest_claims(db: sqlite3.Connection, claims_path: Path, redactor=None, stats=None) -> int:
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

            # Apply redaction to text field if redactor is provided
            text = obj["text"]
            if redactor:
                text = redactor.redact(text, stats)

            db.execute(
                """
                INSERT INTO claim(claim_id,paper_id,claim_type,text,confidence,status,
                                  verification_status,verification_mode,parent_claim_id,frame_id,
                                  informant_coverage,contradicting_count,saturation_note,prevalence_basis,
                                  created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
                  informant_coverage=COALESCE(excluded.informant_coverage, claim.informant_coverage),
                  contradicting_count=COALESCE(excluded.contradicting_count, claim.contradicting_count),
                  saturation_note=COALESCE(excluded.saturation_note, claim.saturation_note),
                  prevalence_basis=COALESCE(excluded.prevalence_basis, claim.prevalence_basis),
                  updated_at=excluded.updated_at
                """,
                (
                    obj["claim_id"],
                    obj["paper_id"],
                    claim_type,
                    text,  # potentially redacted
                    obj.get("confidence", 0.5),
                    obj.get("status","draft"),
                    obj.get("verification_status", "unverified"),
                    obj.get("verification_mode","public_provenance"),
                    obj.get("parent_claim_id"),
                    obj.get("frame_id"),
                    obj.get("informant_coverage"),
                    obj.get("contradicting_count", 0),
                    obj.get("saturation_note"),
                    obj.get("prevalence_basis"),
                    now(),
                    now(),
                ),
            )
            n += 1
    db.commit()
    return n

def ingest_evidence(db: sqlite3.Connection, evidence_path: Path, redactor=None, stats=None) -> int:
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

            # Apply redaction to summary field if redactor is provided
            summary = obj["summary"]
            if redactor:
                summary = redactor.redact(summary, stats)
                # Also redact string values in meta
                for key, val in meta.items():
                    if isinstance(val, str):
                        meta[key] = redactor.redact(val, stats)

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
                    summary,  # potentially redacted
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

    # Set up optional redaction
    redactor = None
    redact_stats = None
    if args.entities:
        if not HAS_REDACT:
            die("redact.py module not found. Ensure redact.py is in the same directory as lp.py")
        entities_p = Path(args.entities).resolve()
        if not entities_p.exists():
            die(f"entities file not found: {entities_p}")
        redactor = EntityRedactor(entities_path=entities_p)
        redact_stats = RedactionStats()

    nc = ingest_claims(db, claims_p, redactor=redactor, stats=redact_stats)
    ne = ingest_evidence(db, evidence_p, redactor=redactor, stats=redact_stats)
    nl = ingest_links(db, links_p)

    print(f"[living_paper] ingested: {nc} claims, {ne} evidence items, {nl} links into {pub_path}")
    if redact_stats and redact_stats.total_redactions > 0:
        print(f"[living_paper] redacted {redact_stats.total_redactions} entities during ingest")

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


def export_html_cmd(args: argparse.Namespace) -> None:
    """Export a self-contained HTML reviewer interface (no server needed)."""
    pub_path, _ = db_paths()
    if not pub_path.exists():
        die(f"database not found: {pub_path} — run 'lp.py init' first")

    db = connect(pub_path)

    # Gather all data
    paper_id = args.paper
    paper = db.execute("SELECT * FROM paper WHERE paper_id = ?", (paper_id,)).fetchone()
    if not paper:
        die(f"paper not found: {paper_id}")

    claims = db.execute("""
        SELECT claim_id, paper_id, claim_type, text, confidence, status,
               verification_status, verified_by, verified_at,
               informant_coverage, contradicting_count, saturation_note, prevalence_basis
        FROM claim WHERE paper_id = ? ORDER BY claim_id
    """, (paper_id,)).fetchall()

    # Build claims data with evidence
    claims_data = []
    for c in claims:
        links = db.execute("""
            SELECT l.evidence_id, l.relation, l.weight, l.note, l.analytic_note,
                   l.verification_status, l.verified_by, l.verified_at,
                   e.summary, e.sensitivity_tier, e.evidence_type, e.meta_json
            FROM claim_evidence_link l
            JOIN evidence e ON e.evidence_id = l.evidence_id
            WHERE l.claim_id = ?
            ORDER BY CASE l.weight WHEN 'central' THEN 1 WHEN 'supporting' THEN 2 ELSE 3 END, l.relation
        """, (c['claim_id'],)).fetchall()

        evidence_list = []
        for l in links:
            # Extract direction from meta_json for contradiction flagging
            meta = json.loads(l['meta_json'] or '{}')
            direction = meta.get('direction', '').upper()
            is_contradicting = direction == 'CHALLENGES'

            evidence_list.append({
                'evidence_id': l['evidence_id'],
                'relation': l['relation'],
                'weight': l['weight'],
                'note': l['note'] or '',
                'analytic_note': l['analytic_note'] or '',
                'verification_status': l['verification_status'],
                'verified_by': l['verified_by'],
                'verified_at': l['verified_at'],
                'summary': l['summary'] if l['sensitivity_tier'] == 'PUBLIC' else '[CONTROLLED]',
                'sensitivity_tier': l['sensitivity_tier'],
                'evidence_type': l['evidence_type'],
                'direction': direction,
                'is_contradicting': is_contradicting
            })

        # Compute support status
        supports = sum(1 for l in links if l['relation'] == 'supports')
        challenges = sum(1 for l in links if l['relation'] == 'challenges')
        if challenges > supports:
            support_status = 'contested'
        elif challenges > 0:
            support_status = 'partial'
        elif supports > 0:
            support_status = 'supported'
        else:
            support_status = 'undocumented'

        claims_data.append({
            'claim_id': c['claim_id'],
            'claim_type': c['claim_type'],
            'text': c['text'],
            'confidence': c['confidence'],
            'verification_status': c['verification_status'],
            'informant_coverage': c['informant_coverage'],
            'contradicting_count': c['contradicting_count'],
            'saturation_note': c['saturation_note'],
            'prevalence_basis': c['prevalence_basis'],
            'support_status': support_status,
            'evidence': evidence_list
        })

    # Generate HTML
    data_json = json.dumps({'paper_id': paper_id, 'title': paper['title'], 'claims': claims_data, 'generated_at': now()})

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Review: {paper_id}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; color: #333; line-height: 1.6; }}
        .container {{ max-width: 1000px; margin: 0 auto; padding: 20px; }}
        header {{ background: #1a1a2e; color: white; padding: 20px; margin-bottom: 20px; }}
        header h1 {{ font-size: 1.3rem; font-weight: 500; }}
        header p {{ opacity: 0.8; font-size: 0.85rem; margin-top: 5px; }}
        .reviewer-bar {{ background: white; padding: 15px 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); display: flex; gap: 15px; align-items: center; flex-wrap: wrap; }}
        .reviewer-bar input {{ padding: 8px 12px; border: 1px solid #ddd; border-radius: 4px; font-size: 0.9rem; }}
        .reviewer-bar button {{ padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; font-size: 0.9rem; }}
        .btn-primary {{ background: #1a1a2e; color: white; }}
        .btn-success {{ background: #4caf50; color: white; }}
        .claim-card {{ background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 15px; overflow: hidden; }}
        .claim-header {{ padding: 12px 16px; border-bottom: 1px solid #eee; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }}
        .claim-id {{ font-family: monospace; font-size: 0.75rem; color: #666; background: #f0f0f0; padding: 2px 6px; border-radius: 4px; }}
        .claim-type {{ font-size: 0.65rem; text-transform: uppercase; padding: 2px 6px; border-radius: 4px; background: #e0e0e0; }}
        .claim-type.empirical {{ background: #e3f2fd; color: #1565c0; }}
        .claim-type.theoretical {{ background: #f3e5f5; color: #7b1fa2; }}
        .status-badge {{ font-size: 0.65rem; text-transform: uppercase; padding: 2px 6px; border-radius: 4px; }}
        .status-supported {{ background: #c8e6c9; color: #2e7d32; }}
        .status-partial {{ background: #fff3e0; color: #ef6c00; }}
        .status-contested {{ background: #ffcdd2; color: #c62828; }}
        .status-undocumented {{ background: #e0e0e0; color: #616161; }}
        .claim-body {{ padding: 12px 16px; }}
        .claim-text {{ font-size: 0.95rem; margin-bottom: 10px; }}
        .prevalence {{ padding: 8px 10px; background: #f8f9fa; border-radius: 4px; font-size: 0.75rem; color: #555; margin-bottom: 10px; }}
        .evidence-list {{ padding: 0 16px 16px; }}
        .evidence-item {{ padding: 10px; margin-bottom: 8px; background: #fafafa; border-radius: 6px; border-left: 3px solid #ccc; }}
        .evidence-item.supports {{ border-left-color: #4caf50; }}
        .evidence-item.challenges {{ border-left-color: #f44336; }}
        .evidence-item.qualifies {{ border-left-color: #ff9800; }}
        .evidence-item.contradicting {{ background: #fff3f3; border-left-color: #f44336; border-left-width: 4px; }}
        .contradiction-badge {{ background: #f44336; color: white; font-size: 0.6rem; padding: 2px 6px; border-radius: 3px; font-weight: bold; margin-left: 8px; }}
        .evidence-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }}
        .evidence-id {{ font-family: monospace; font-size: 0.7rem; color: #666; }}
        .evidence-relation {{ font-size: 0.6rem; text-transform: uppercase; padding: 2px 5px; border-radius: 3px; background: #e0e0e0; }}
        .evidence-summary {{ font-size: 0.85rem; color: #444; }}
        .note-input {{ width: 100%; margin-top: 8px; padding: 8px; border: 1px solid #ddd; border-radius: 4px; font-size: 0.8rem; resize: vertical; min-height: 50px; }}
        .verify-controls {{ display: flex; gap: 6px; margin-top: 8px; }}
        .verify-btn {{ padding: 5px 10px; border: none; border-radius: 4px; cursor: pointer; font-size: 0.75rem; }}
        .verify-btn.verified {{ background: #4caf50; color: white; }}
        .verify-btn.author {{ background: #ff9800; color: white; }}
        .verify-btn.unverified {{ background: #9e9e9e; color: white; }}
        .verify-btn.active {{ box-shadow: 0 0 0 2px #333; }}
        .stats {{ display: flex; gap: 15px; font-size: 0.85rem; color: #666; margin-bottom: 15px; }}
    </style>
</head>
<body>
    <header>
        <div class="container">
            <h1>Verification Review: {paper_id}</h1>
            <p>Offline reviewer interface - your progress is saved locally</p>
        </div>
    </header>
    <div class="container">
        <div class="reviewer-bar">
            <label>Your name: <input type="text" id="reviewer-name" placeholder="Reviewer name"></label>
            <button class="btn-success" onclick="generateReport()">Generate Report</button>
            <button class="btn-primary" onclick="exportData()">Export Data</button>
            <span id="save-status" style="font-size: 0.8rem; color: #666;"></span>
        </div>
        <div class="stats" id="stats"></div>
        <div id="claims"></div>
    </div>
    <script>
    const DATA = {data_json};
    const STORAGE_KEY = 'lp_review_' + DATA.paper_id;

    let state = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{{"verifications":{{}},"notes":{{}}}}');
    let reviewerName = localStorage.getItem('reviewerName') || '';
    document.getElementById('reviewer-name').value = reviewerName;
    document.getElementById('reviewer-name').addEventListener('change', e => {{
        reviewerName = e.target.value;
        localStorage.setItem('reviewerName', reviewerName);
    }});

    function saveState() {{
        localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
        document.getElementById('save-status').textContent = 'Saved ' + new Date().toLocaleTimeString();
    }}

    function setVerification(claimId, evidenceId, status) {{
        const key = claimId + ':' + evidenceId;
        state.verifications[key] = {{ status, reviewer: reviewerName, at: new Date().toISOString() }};
        saveState();
        render();
    }}

    function updateNote(claimId, evidenceId, note) {{
        const key = claimId + ':' + evidenceId;
        state.notes[key] = note;
        saveState();
    }}

    function render() {{
        let verified = 0, author = 0, unverified = 0;
        let html = '';
        DATA.claims.forEach(c => {{
            html += `<div class="claim-card">
                <div class="claim-header">
                    <span class="claim-id">${{c.claim_id}}</span>
                    <span class="claim-type ${{c.claim_type}}">${{c.claim_type}}</span>
                    <span class="status-badge status-${{c.support_status}}">${{c.support_status}}</span>
                </div>
                <div class="claim-body">
                    <p class="claim-text">${{c.text}}</p>
                    ${{(c.informant_coverage || c.saturation_note || c.prevalence_basis) ? `
                    <div class="prevalence">
                        <strong>Prevalence:</strong>
                        ${{c.informant_coverage ? ' ' + c.informant_coverage : ''}}
                        ${{c.prevalence_basis ? ' [' + c.prevalence_basis + ']' : ''}}
                        ${{c.contradicting_count === 0 ? ' - No contradicting' : c.contradicting_count > 0 ? ' - ' + c.contradicting_count + ' contradicting' : ''}}
                        ${{c.saturation_note ? '<br><em>' + c.saturation_note + '</em>' : ''}}
                    </div>` : ''}}
                </div>
                <div class="evidence-list">
                    <strong style="font-size: 0.8rem; color: #666;">Evidence (${{c.evidence.length}})</strong>
                    ${{c.evidence.map(e => {{
                        const key = c.claim_id + ':' + e.evidence_id;
                        const v = state.verifications[key] || {{}};
                        const note = state.notes[key] || e.analytic_note || '';
                        if (v.status === 'external_verified') verified++;
                        else if (v.status === 'author_verified') author++;
                        else unverified++;
                        return `<div class="evidence-item ${{e.relation}} ${{e.is_contradicting ? 'contradicting' : ''}}">
                            <div class="evidence-header">
                                <span class="evidence-id">${{e.evidence_id}}${{e.is_contradicting ? '<span class="contradiction-badge">CONTRADICTING</span>' : ''}}</span>
                                <span><span class="evidence-relation">${{e.relation}}</span> <span class="evidence-relation">${{e.weight}}</span></span>
                            </div>
                            <p class="evidence-summary">${{e.summary}}</p>
                            ${{e.note ? '<p style="font-size:0.75rem;color:#666;margin-top:4px;">Note: ' + e.note + '</p>' : ''}}
                            <textarea class="note-input" placeholder="Your analytic note..." onchange="updateNote('${{c.claim_id}}','${{e.evidence_id}}',this.value)">${{note}}</textarea>
                            <div class="verify-controls">
                                <button class="verify-btn verified ${{v.status==='external_verified'?'active':''}}" onclick="setVerification('${{c.claim_id}}','${{e.evidence_id}}','external_verified')">Verified</button>
                                <button class="verify-btn author ${{v.status==='author_verified'?'active':''}}" onclick="setVerification('${{c.claim_id}}','${{e.evidence_id}}','author_verified')">Author Only</button>
                                <button class="verify-btn unverified ${{v.status==='unverified'?'active':''}}" onclick="setVerification('${{c.claim_id}}','${{e.evidence_id}}','unverified')">Not Verified</button>
                            </div>
                        </div>`;
                    }}).join('')}}
                </div>
            </div>`;
        }});
        document.getElementById('claims').innerHTML = html;
        document.getElementById('stats').innerHTML = `
            <span>Verified: ${{verified}}</span>
            <span>Author Only: ${{author}}</span>
            <span>Not Verified: ${{unverified}}</span>
            <span>Total Links: ${{verified + author + unverified}}</span>
        `;
    }}

    function generateReport() {{
        let report = '# Verification Report: ' + DATA.paper_id + '\\n\\n';
        report += 'Generated: ' + new Date().toISOString() + '\\n';
        report += 'Reviewer: ' + (reviewerName || 'anonymous') + '\\n\\n';

        let verified = 0, author = 0, unverified = 0;
        DATA.claims.forEach(c => {{
            c.evidence.forEach(e => {{
                const key = c.claim_id + ':' + e.evidence_id;
                const v = state.verifications[key] || {{}};
                if (v.status === 'external_verified') verified++;
                else if (v.status === 'author_verified') author++;
                else unverified++;
            }});
        }});

        report += '## Summary\\n\\n';
        report += '- Verified: ' + verified + '\\n';
        report += '- Author Only: ' + author + '\\n';
        report += '- Not Verified: ' + unverified + '\\n\\n';

        report += '## Claims Detail\\n\\n';
        DATA.claims.forEach(c => {{
            report += '### ' + c.claim_id + '\\n';
            report += '**' + c.text + '**\\n\\n';
            c.evidence.forEach(e => {{
                const key = c.claim_id + ':' + e.evidence_id;
                const v = state.verifications[key] || {{}};
                const note = state.notes[key] || '';
                const icon = v.status === 'external_verified' ? '[V]' : v.status === 'author_verified' ? '[A]' : '[ ]';
                report += '- ' + icon + ' ' + e.evidence_id + ' (' + e.relation + ')\\n';
                if (note) report += '  - *Note:* ' + note + '\\n';
            }});
            report += '\\n';
        }});

        const blob = new Blob([report], {{ type: 'text/markdown' }});
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'verification_report_' + DATA.paper_id + '_' + new Date().toISOString().slice(0,10) + '.md';
        a.click();
        URL.revokeObjectURL(url);
    }}

    function exportData() {{
        const exportObj = {{ paper_id: DATA.paper_id, reviewer: reviewerName, exported_at: new Date().toISOString(), verifications: state.verifications, notes: state.notes }};
        const blob = new Blob([JSON.stringify(exportObj, null, 2)], {{ type: 'application/json' }});
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'review_data_' + DATA.paper_id + '_' + new Date().toISOString().slice(0,10) + '.json';
        a.click();
        URL.revokeObjectURL(url);
    }}

    render();
    </script>
</body>
</html>'''

    out_path = Path(args.out)
    out_path.write_text(html, encoding='utf-8')
    print(f"[living_paper] static HTML reviewer exported: {out_path}")
    print(f"  - {len(claims_data)} claims, {sum(len(c['evidence']) for c in claims_data)} evidence links")
    print(f"  - Open in any browser, no server needed")
    print(f"  - Reviewer progress saved in browser localStorage")


def export_package_cmd(args: argparse.Namespace) -> None:
    """Export a reviewer package folder with HTML, launchers, and README."""
    import stat

    pub_path, _ = db_paths()
    if not pub_path.exists():
        die(f"database not found: {pub_path} — run 'lp.py init' first")

    paper_id = args.paper
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # First generate the HTML using export_html_cmd logic
    html_path = out_dir / "review.html"

    # Create a mock args object for export_html_cmd
    class HtmlArgs:
        pass
    html_args = HtmlArgs()
    html_args.paper = paper_id
    html_args.out = str(html_path)

    export_html_cmd(html_args)

    # Create README.txt
    readme = f"""LIVING PAPER VERIFICATION REVIEW
================================

Paper: {paper_id}

HOW TO USE THIS REVIEW INTERFACE
--------------------------------

1. OPEN THE REVIEW
   - Double-click "Open Review" (Mac) or "Open Review.bat" (Windows)
   - Or just open "review.html" directly in your web browser

2. DO YOUR REVIEW
   - Enter your name at the top
   - For each claim-evidence link, click one of:
     - "Verified" = you independently confirm this evidence supports the claim
     - "Author Only" = evidence exists but you cannot independently verify
     - "Not Verified" = you have concerns about this link
   - Add notes in the text boxes as needed

3. GENERATE YOUR REPORT
   - Click the green "Generate Report" button at the top
   - A markdown file will download automatically
   - Send this file back to the author(s)

YOUR PROGRESS IS AUTO-SAVED
---------------------------
Your work is saved in your browser's local storage. You can close
the browser and come back later - your progress will still be there.

If you need to review on a different computer, use "Export Data"
to save your progress as a JSON file.

QUESTIONS?
----------
Contact the paper author(s) if you have any questions about
the verification process.

"""
    readme_path = out_dir / "README.txt"
    readme_path.write_text(readme, encoding='utf-8')

    # Create Mac launcher (.command file)
    mac_launcher = f'''#!/bin/bash
# Open the Living Paper review interface
cd "$(dirname "$0")"
open review.html
'''
    mac_path = out_dir / "Open Review.command"
    mac_path.write_text(mac_launcher, encoding='utf-8')
    # Make executable
    mac_path.chmod(mac_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    # Create Windows launcher (.bat file)
    win_launcher = '''@echo off
REM Open the Living Paper review interface
start "" "%~dp0review.html"
'''
    win_path = out_dir / "Open Review.bat"
    win_path.write_text(win_launcher, encoding='utf-8')

    print(f"[living_paper] reviewer package created: {out_dir}/")
    print(f"  - review.html        (the review interface)")
    print(f"  - README.txt         (instructions for reviewers)")
    print(f"  - Open Review.command (Mac launcher)")
    print(f"  - Open Review.bat    (Windows launcher)")
    print(f"\nShare this folder with reviewers - they just double-click to start.")


def redact_cmd(args: argparse.Namespace) -> None:
    """Wrapper for redaction commands (author tool)."""
    if not HAS_REDACT:
        die("redact.py module not found. Ensure redact.py is in the same directory as lp.py")

    from redact import EntityRedactor, RedactionStats, load_jsonl, save_jsonl

    entities_p = Path(args.entities).resolve()
    if not entities_p.exists():
        die(f"entities file not found: {entities_p}")

    redactor = EntityRedactor(entities_path=entities_p)

    if args.redact_cmd == "check":
        # Preview what would be redacted
        input_p = Path(args.input).resolve()
        if not input_p.exists():
            die(f"input file not found: {input_p}")

        records = load_jsonl(input_p)
        stats = RedactionStats()

        for record in records:
            redactor.redact_jsonl_record(record, stats=stats)

        print(redactor.generate_report(stats))
        if stats.total_redactions > 0:
            print(f"\n[redact] Would redact {stats.total_redactions} entities in {len(records)} records")
        else:
            print(f"\n[redact] No entities to redact in {len(records)} records")

    elif args.redact_cmd == "apply":
        # Apply redaction to file
        input_p = Path(args.input).resolve()
        output_p = Path(args.output).resolve()
        if not input_p.exists():
            die(f"input file not found: {input_p}")

        records = load_jsonl(input_p)
        stats = RedactionStats()

        redacted_records = [redactor.redact_jsonl_record(r, stats=stats) for r in records]
        save_jsonl(redacted_records, output_p)

        print(f"[redact] Redacted {stats.total_redactions} entities across {len(records)} records")
        print(f"[redact] Output: {output_p}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="lp", description="living_paper v0.5")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="initialize DBs and policies")

    ing = sub.add_parser("ingest", help="ingest claims/evidence/links")
    ing.add_argument("--claims", required=True)
    ing.add_argument("--evidence", required=True)
    ing.add_argument("--links", required=True)
    ing.add_argument("--entities", help="optional entities YAML/JSON for PII redaction during ingest")

    sub.add_parser("lint", help="run traceability checks")

    ex = sub.add_parser("export", help="export PUBLIC provenance + summaries")
    ex.add_argument("--out", required=True)

    vex = sub.add_parser("verify-export", help="export verification package for external reviewers")
    vex.add_argument("--out", required=True)

    pre = sub.add_parser("prereview", help="generate pre-review report of contested claims")
    pre.add_argument("--out", required=True)

    html = sub.add_parser("export-html", help="export self-contained HTML reviewer (no server)")
    html.add_argument("--paper", required=True, help="paper_id to export")
    html.add_argument("--out", required=True, help="output HTML file path")

    pkg = sub.add_parser("export-package", help="export reviewer package folder (HTML + launchers + README)")
    pkg.add_argument("--paper", required=True, help="paper_id to export")
    pkg.add_argument("--out", required=True, help="output folder path")

    # Redaction commands (author tools)
    redact_p = sub.add_parser("redact", help="redact entities from JSONL files (author tool)")
    redact_sub = redact_p.add_subparsers(dest="redact_cmd", required=True)

    rc = redact_sub.add_parser("check", help="preview what would be redacted")
    rc.add_argument("--input", "-i", required=True, help="input JSONL file")
    rc.add_argument("--entities", "-e", required=True, help="entities YAML/JSON file")

    ra = redact_sub.add_parser("apply", help="apply redaction to file")
    ra.add_argument("--input", "-i", required=True, help="input JSONL file")
    ra.add_argument("--output", "-o", required=True, help="output JSONL file")
    ra.add_argument("--entities", "-e", required=True, help="entities YAML/JSON file")

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
    elif args.cmd == "export-html":
        export_html_cmd(args)
    elif args.cmd == "export-package":
        export_package_cmd(args)
    elif args.cmd == "redact":
        redact_cmd(args)
    else:
        die(f"unknown command: {args.cmd}")

if __name__ == "__main__":
    main()
