#!/usr/bin/env python3
"""
vault.py - Protected evidence storage with tiered access

Manages evidence across three tiers:
- PUBLIC: Non-identifying summaries, safe to share
- CONTROLLED: Anonymized content, approved reviewers only
- WITNESS_ONLY: Raw content with PII, author + designated witness only

Usage:
    python vault.py init --project <path>
    python vault.py ingest --source <file> --tier <tier> --mappings <mappings.json>
    python vault.py query --evidence-id <id> --tier <tier>
    python vault.py export --tier PUBLIC --out <dir>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from hasher import PIIMappings, PIIScanner, hash_content, generate_summary

ISO = "%Y-%m-%dT%H:%M:%SZ"


def now() -> str:
    return datetime.utcnow().strftime(ISO)


def die(msg: str, code: int = 2) -> None:
    print(f"[vault] ERROR: {msg}", file=sys.stderr)
    raise SystemExit(code)


@dataclass
class EvidenceItem:
    """A piece of evidence at a specific tier."""
    evidence_id: str
    evidence_type: str  # quote, fieldnote, observation, quant_output
    tier: str           # PUBLIC, CONTROLLED, WITNESS_ONLY
    content_hash: str   # SHA-256 of raw content + nonce
    nonce: str          # stored in private DB only
    summary: str        # non-identifying summary (PUBLIC tier)
    anonymized: str     # PII-replaced content (CONTROLLED tier)
    raw: str            # original content (WITNESS_ONLY tier)
    source_file: Optional[str] = None
    source_line_start: Optional[int] = None
    source_line_end: Optional[int] = None
    meta: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=now)


class Vault:
    """
    Evidence vault with tiered access control.

    Uses two SQLite databases:
    - public.sqlite: PUBLIC tier data (summaries, hashes, metadata)
    - private.sqlite: CONTROLLED + WITNESS_ONLY data (anonymized/raw content, nonces)
    """

    def __init__(self, project_path: Path):
        self.project_path = project_path
        self.vault_dir = project_path / "analysis" / "vault"
        self.vault_dir.mkdir(parents=True, exist_ok=True)

        self.public_db_path = self.vault_dir / "public.sqlite"
        self.private_db_path = self.vault_dir / "private.sqlite"

        self._public_db: Optional[sqlite3.Connection] = None
        self._private_db: Optional[sqlite3.Connection] = None

    def _connect(self, path: Path) -> sqlite3.Connection:
        db = sqlite3.connect(str(path))
        db.row_factory = sqlite3.Row
        return db

    @property
    def public_db(self) -> sqlite3.Connection:
        if self._public_db is None:
            self._public_db = self._connect(self.public_db_path)
        return self._public_db

    @property
    def private_db(self) -> sqlite3.Connection:
        if self._private_db is None:
            self._private_db = self._connect(self.private_db_path)
        return self._private_db

    def init(self) -> None:
        """Initialize vault databases."""
        # Public schema: safe to share
        self.public_db.executescript("""
            PRAGMA journal_mode=WAL;

            CREATE TABLE IF NOT EXISTS evidence_public (
                evidence_id TEXT PRIMARY KEY,
                paper_id TEXT,
                evidence_type TEXT NOT NULL,
                tier TEXT NOT NULL CHECK (tier IN ('PUBLIC','CONTROLLED','WITNESS_ONLY')),
                content_hash TEXT NOT NULL,
                summary TEXT NOT NULL,
                source_file_hash TEXT,
                source_line_start INTEGER,
                source_line_end INTEGER,
                meta_json TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS verification_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                evidence_id TEXT NOT NULL,
                verifier_id TEXT,
                verification_type TEXT,
                result TEXT,
                notes TEXT,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_evidence_tier ON evidence_public(tier);
            CREATE INDEX IF NOT EXISTS idx_evidence_type ON evidence_public(evidence_type);
        """)
        self.public_db.commit()

        # Private schema: protected
        self.private_db.executescript("""
            PRAGMA journal_mode=WAL;

            CREATE TABLE IF NOT EXISTS evidence_private (
                evidence_id TEXT PRIMARY KEY,
                nonce TEXT NOT NULL,
                anonymized_content TEXT,
                raw_content TEXT,
                source_file_path TEXT,
                pii_mappings_snapshot TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS access_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                evidence_id TEXT NOT NULL,
                accessor_id TEXT,
                tier_accessed TEXT,
                purpose TEXT,
                created_at TEXT NOT NULL
            );
        """)
        self.private_db.commit()

        # Create .gitignore for private db
        gitignore = self.vault_dir / ".gitignore"
        if not gitignore.exists():
            gitignore.write_text("private.sqlite\npii_mappings.json\n")

        print(f"[vault] initialized at {self.vault_dir}")

    def store(self, item: EvidenceItem, paper_id: str = "default") -> None:
        """Store evidence item in appropriate tier."""
        # Hash source file path
        source_hash = None
        if item.source_file:
            source_hash = hashlib.sha256(item.source_file.encode()).hexdigest()[:16]

        # Public tier data
        self.public_db.execute("""
            INSERT OR REPLACE INTO evidence_public
            (evidence_id, paper_id, evidence_type, tier, content_hash, summary,
             source_file_hash, source_line_start, source_line_end, meta_json,
             created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item.evidence_id,
            paper_id,
            item.evidence_type,
            item.tier,
            item.content_hash,
            item.summary,
            source_hash,
            item.source_line_start,
            item.source_line_end,
            json.dumps(item.meta),
            item.created_at,
            now()
        ))
        self.public_db.commit()

        # Private tier data
        self.private_db.execute("""
            INSERT OR REPLACE INTO evidence_private
            (evidence_id, nonce, anonymized_content, raw_content,
             source_file_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            item.evidence_id,
            item.nonce,
            item.anonymized if item.tier in ('CONTROLLED', 'WITNESS_ONLY') else None,
            item.raw if item.tier == 'WITNESS_ONLY' else None,
            item.source_file,
            item.created_at
        ))
        self.private_db.commit()

    def get_public(self, evidence_id: str) -> Optional[Dict]:
        """Get public tier data for evidence."""
        row = self.public_db.execute(
            "SELECT * FROM evidence_public WHERE evidence_id = ?",
            (evidence_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_controlled(self, evidence_id: str, accessor_id: str, purpose: str) -> Optional[Dict]:
        """Get controlled tier data (logs access)."""
        # Get public data
        pub = self.get_public(evidence_id)
        if not pub:
            return None

        # Get private data
        priv = self.private_db.execute(
            "SELECT anonymized_content FROM evidence_private WHERE evidence_id = ?",
            (evidence_id,)
        ).fetchone()

        if not priv:
            return None

        # Log access
        self.private_db.execute("""
            INSERT INTO access_log (evidence_id, accessor_id, tier_accessed, purpose, created_at)
            VALUES (?, ?, 'CONTROLLED', ?, ?)
        """, (evidence_id, accessor_id, purpose, now()))
        self.private_db.commit()

        return {
            **pub,
            'anonymized_content': priv['anonymized_content']
        }

    def get_witness_only(self, evidence_id: str, accessor_id: str, purpose: str) -> Optional[Dict]:
        """Get witness-only tier data (logs access, requires authorization)."""
        pub = self.get_public(evidence_id)
        if not pub:
            return None

        priv = self.private_db.execute(
            "SELECT raw_content, source_file_path FROM evidence_private WHERE evidence_id = ?",
            (evidence_id,)
        ).fetchone()

        if not priv:
            return None

        # Log access
        self.private_db.execute("""
            INSERT INTO access_log (evidence_id, accessor_id, tier_accessed, purpose, created_at)
            VALUES (?, ?, 'WITNESS_ONLY', ?, ?)
        """, (evidence_id, accessor_id, purpose, now()))
        self.private_db.commit()

        return {
            **pub,
            'raw_content': priv['raw_content'],
            'source_file_path': priv['source_file_path']
        }

    def verify_hash(self, evidence_id: str, content: str) -> bool:
        """Verify that content matches stored hash."""
        priv = self.private_db.execute(
            "SELECT nonce FROM evidence_private WHERE evidence_id = ?",
            (evidence_id,)
        ).fetchone()

        if not priv:
            return False

        pub = self.get_public(evidence_id)
        if not pub:
            return False

        computed, _ = hash_content(content, priv['nonce'])
        return computed == pub['content_hash']

    def log_verification(self, evidence_id: str, verifier_id: str,
                         verification_type: str, result: str, notes: str = None) -> None:
        """Log a verification event."""
        self.public_db.execute("""
            INSERT INTO verification_log
            (evidence_id, verifier_id, verification_type, result, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (evidence_id, verifier_id, verification_type, result, notes, now()))
        self.public_db.commit()

    def export_public(self, out_dir: Path) -> None:
        """Export all PUBLIC tier data."""
        out_dir.mkdir(parents=True, exist_ok=True)

        rows = self.public_db.execute("""
            SELECT * FROM evidence_public WHERE tier = 'PUBLIC'
        """).fetchall()

        # Export as JSONL
        jsonl_path = out_dir / "evidence_public.jsonl"
        with open(jsonl_path, 'w') as f:
            for row in rows:
                f.write(json.dumps(dict(row)) + '\n')

        # Export summary markdown
        md_path = out_dir / "evidence_summary.md"
        with open(md_path, 'w') as f:
            f.write("# Evidence Summary (PUBLIC tier)\n\n")
            f.write(f"Generated: {now()}\n\n")
            f.write(f"Total items: {len(rows)}\n\n")

            for row in rows:
                f.write(f"## {row['evidence_id']}\n\n")
                f.write(f"- Type: {row['evidence_type']}\n")
                f.write(f"- Hash: `{row['content_hash'][:16]}...`\n")
                f.write(f"- Summary: {row['summary']}\n\n")

        print(f"[vault] exported {len(rows)} items to {out_dir}")

    def stats(self) -> Dict:
        """Get vault statistics."""
        public_count = self.public_db.execute(
            "SELECT tier, COUNT(*) as n FROM evidence_public GROUP BY tier"
        ).fetchall()

        verification_count = self.public_db.execute(
            "SELECT COUNT(*) as n FROM verification_log"
        ).fetchone()

        access_count = self.private_db.execute(
            "SELECT tier_accessed, COUNT(*) as n FROM access_log GROUP BY tier_accessed"
        ).fetchall()

        return {
            'by_tier': {row['tier']: row['n'] for row in public_count},
            'verifications': verification_count['n'] if verification_count else 0,
            'access_by_tier': {row['tier_accessed']: row['n'] for row in access_count}
        }


def ingest_from_audit(vault: Vault, audit_dir: Path, mappings: PIIMappings,
                      paper_id: str) -> int:
    """
    Ingest evidence from existing audit output files.

    Reads evidence.jsonl, applies anonymization, stores in vault.
    """
    evidence_path = audit_dir / "evidence.jsonl"
    if not evidence_path.exists():
        die(f"evidence.jsonl not found in {audit_dir}")

    scanner = PIIScanner(mappings)
    count = 0

    with open(evidence_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            obj = json.loads(line)

            # Get raw content (try multiple field names)
            raw = obj.get('content') or obj.get('text') or obj.get('quote') or ''
            if not raw:
                continue

            # Generate tiers
            # 1. Hash the raw content
            content_hash, nonce = hash_content(raw)

            # 2. Anonymize
            anonymized = scanner.anonymize(raw)

            # 3. Generate summary
            summary = generate_summary(anonymized, max_words=25)

            # Determine tier based on content
            # If anonymization changed the text significantly, it had PII
            has_pii = anonymized != raw
            tier = 'CONTROLLED' if has_pii else 'PUBLIC'

            # Create evidence item
            item = EvidenceItem(
                evidence_id=obj.get('evidence_id', f"ev_{count:04d}"),
                evidence_type=obj.get('evidence_type', 'quote'),
                tier=tier,
                content_hash=content_hash,
                nonce=nonce,
                summary=summary,
                anonymized=anonymized,
                raw=raw,
                source_file=obj.get('source_file'),
                source_line_start=obj.get('line_start'),
                source_line_end=obj.get('line_end'),
                meta={
                    'original_id': obj.get('evidence_id'),
                    'informant_role': obj.get('informant_role'),
                    'site': obj.get('site'),
                }
            )

            vault.store(item, paper_id)
            count += 1

    return count


# CLI

def init_cmd(args):
    """Initialize vault."""
    project_path = Path(args.project).resolve()
    vault = Vault(project_path)
    vault.init()


def ingest_cmd(args):
    """Ingest evidence from audit files."""
    project_path = Path(args.project).resolve()
    vault = Vault(project_path)

    # Load mappings
    if args.mappings:
        mappings = PIIMappings.from_json(Path(args.mappings).read_text())
    else:
        # Try to find project config
        config_path = project_path / "project_config.yaml"
        if config_path.exists():
            mappings = PIIMappings.from_project_config(config_path)
        else:
            mappings = PIIMappings()

    # Add known names if provided
    if args.names:
        for name in args.names.split(','):
            name = name.strip()
            if name:
                mappings.project_names.add(name)
                mappings.add(name, 'name')

    audit_dir = Path(args.audit_dir).resolve()
    paper_id = args.paper_id or project_path.name

    count = ingest_from_audit(vault, audit_dir, mappings, paper_id)
    print(f"[vault] ingested {count} evidence items from {audit_dir}")

    # Save mappings snapshot
    mappings_path = vault.vault_dir / "pii_mappings.json"
    mappings_path.write_text(mappings.to_json())
    print(f"[vault] mappings saved to {mappings_path}")


def export_cmd(args):
    """Export public tier."""
    project_path = Path(args.project).resolve()
    vault = Vault(project_path)

    out_dir = Path(args.out).resolve()
    vault.export_public(out_dir)


def stats_cmd(args):
    """Show vault statistics."""
    project_path = Path(args.project).resolve()
    vault = Vault(project_path)

    stats = vault.stats()
    print(f"[vault] statistics for {project_path.name}:")
    print(f"  By tier: {stats['by_tier']}")
    print(f"  Verifications: {stats['verifications']}")
    print(f"  Access by tier: {stats['access_by_tier']}")


def main():
    parser = argparse.ArgumentParser(description='Evidence vault with tiered access')
    sub = parser.add_subparsers(dest='cmd', required=True)

    # init
    init_p = sub.add_parser('init', help='Initialize vault')
    init_p.add_argument('--project', '-p', required=True, help='Project path')

    # ingest
    ing_p = sub.add_parser('ingest', help='Ingest from audit files')
    ing_p.add_argument('--project', '-p', required=True, help='Project path')
    ing_p.add_argument('--audit-dir', '-a', required=True, help='Audit directory')
    ing_p.add_argument('--mappings', '-m', help='PII mappings file')
    ing_p.add_argument('--paper-id', help='Paper ID (default: project name)')
    ing_p.add_argument('--names', help='Additional names (comma-separated)')

    # export
    exp_p = sub.add_parser('export', help='Export public tier')
    exp_p.add_argument('--project', '-p', required=True, help='Project path')
    exp_p.add_argument('--out', '-o', required=True, help='Output directory')

    # stats
    stat_p = sub.add_parser('stats', help='Show vault statistics')
    stat_p.add_argument('--project', '-p', required=True, help='Project path')

    args = parser.parse_args()

    if args.cmd == 'init':
        init_cmd(args)
    elif args.cmd == 'ingest':
        ingest_cmd(args)
    elif args.cmd == 'export':
        export_cmd(args)
    elif args.cmd == 'stats':
        stats_cmd(args)


if __name__ == '__main__':
    main()
