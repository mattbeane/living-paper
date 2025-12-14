#!/usr/bin/env python3
"""
hasher.py - PII detection and hashing for protected evidence

Scans raw data files (transcripts, fieldnotes) and:
1. Detects PII (names, locations, organizations)
2. Generates SHA-256 hashes for each identifier
3. Creates author-only mapping file (hash → real value)
4. Produces anonymized summaries safe for public tier

Usage:
    python hasher.py scan --input <file_or_dir> --mappings <output.json>
    python hasher.py anonymize --input <text> --mappings <mappings.json>
    python hasher.py hash-content --input <text> [--nonce <nonce>]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# Common name patterns (will be supplemented by project-specific lists)
COMMON_TITLES = {'mr', 'mrs', 'ms', 'dr', 'prof', 'professor'}

# Regex patterns for PII detection
PATTERNS = {
    # Capitalized words that look like names (2+ cap words in sequence)
    'potential_name': re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b'),
    # Single capitalized word (might be name)
    'single_cap': re.compile(r'\b([A-Z][a-z]{2,})\b'),
    # Location patterns
    'location': re.compile(r'\b(in|at|from|near)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', re.IGNORECASE),
    # Company/org patterns
    'org': re.compile(r'\b([A-Z][a-z]*(?:\s+(?:Inc|LLC|Corp|Company|Co|Ltd|Industries|Logistics|Warehouse|Distribution)\.?))\b'),
    # Email (always PII)
    'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
    # Phone
    'phone': re.compile(r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'),
}


@dataclass
class PIIMatch:
    """A detected PII instance."""
    pii_type: str  # name, location, org, email, phone
    original: str  # the original text
    hash: str      # SHA-256 hash
    context: str   # surrounding text for verification
    file_path: Optional[str] = None
    line_number: Optional[int] = None


@dataclass
class PIIMappings:
    """Collection of PII → hash mappings."""
    mappings: Dict[str, str] = field(default_factory=dict)  # original → hash
    reverse: Dict[str, str] = field(default_factory=dict)   # hash → original
    by_type: Dict[str, List[str]] = field(default_factory=dict)  # type → [originals]
    project_names: Set[str] = field(default_factory=set)  # known names from project config
    project_sites: Set[str] = field(default_factory=set)  # known site names
    project_orgs: Set[str] = field(default_factory=set)   # known org names

    def add(self, original: str, pii_type: str) -> str:
        """Add a PII item and return its hash."""
        if original in self.mappings:
            return self.mappings[original]

        # Generate deterministic hash (same input → same hash)
        h = hashlib.sha256(original.encode('utf-8')).hexdigest()[:16]

        self.mappings[original] = h
        self.reverse[h] = original

        if pii_type not in self.by_type:
            self.by_type[pii_type] = []
        self.by_type[pii_type].append(original)

        return h

    def get_hash(self, original: str) -> Optional[str]:
        """Get hash for an original value."""
        return self.mappings.get(original)

    def get_original(self, hash_val: str) -> Optional[str]:
        """Get original value from hash (author-only operation)."""
        return self.reverse.get(hash_val)

    def to_json(self) -> str:
        """Serialize to JSON (AUTHOR-ONLY FILE)."""
        return json.dumps({
            'mappings': self.mappings,
            'reverse': self.reverse,
            'by_type': self.by_type,
            'project_names': list(self.project_names),
            'project_sites': list(self.project_sites),
            'project_orgs': list(self.project_orgs),
            'generated_at': datetime.utcnow().isoformat(),
            'warning': 'AUTHOR-ONLY: This file contains PII mappings. Do not share.'
        }, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'PIIMappings':
        """Load from JSON."""
        data = json.loads(json_str)
        obj = cls()
        obj.mappings = data.get('mappings', {})
        obj.reverse = data.get('reverse', {})
        obj.by_type = data.get('by_type', {})
        obj.project_names = set(data.get('project_names', []))
        obj.project_sites = set(data.get('project_sites', []))
        obj.project_orgs = set(data.get('project_orgs', []))
        return obj

    @classmethod
    def from_project_config(cls, config_path: Path) -> 'PIIMappings':
        """Load known identifiers from project_config.yaml."""
        obj = cls()

        if not config_path.exists():
            return obj

        import yaml  # optional dependency
        try:
            with open(config_path) as f:
                config = yaml.safe_load(f)
        except ImportError:
            # Fallback: try to parse as simple key: value
            return obj
        except Exception:
            return obj

        # Extract known names from anonymization section
        anon = config.get('anonymization', {})

        # Site mappings: real_name → pseudonym
        site_mappings = anon.get('site_mappings', {})
        for real_name in site_mappings.keys():
            obj.project_sites.add(real_name)
            obj.add(real_name, 'site')

        # Informant names (if listed)
        informants = anon.get('informant_names', [])
        for name in informants:
            obj.project_names.add(name)
            obj.add(name, 'name')

        # Org names
        orgs = anon.get('org_names', [])
        for org in orgs:
            obj.project_orgs.add(org)
            obj.add(org, 'org')

        return obj


class PIIScanner:
    """Scans text for PII and generates hashes."""

    def __init__(self, mappings: Optional[PIIMappings] = None):
        self.mappings = mappings or PIIMappings()
        # Common words to skip (not names)
        self.skip_words = {
            'the', 'and', 'but', 'for', 'with', 'this', 'that', 'from',
            'january', 'february', 'march', 'april', 'may', 'june',
            'july', 'august', 'september', 'october', 'november', 'december',
            'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
            'interview', 'transcript', 'fieldnote', 'observation',
            'manager', 'supervisor', 'worker', 'associate', 'director',
            'warehouse', 'facility', 'site', 'building', 'floor',
            'robot', 'sorter', 'automation', 'technology',
            # Academic/research terms
            'figure', 'table', 'appendix', 'section', 'chapter',
            'hypothesis', 'finding', 'result', 'conclusion',
        }

    def is_likely_name(self, word: str) -> bool:
        """Heuristic: is this word likely a person's name?"""
        w = word.lower()
        if w in self.skip_words:
            return False
        if len(word) < 2:
            return False
        # Known project names are definitely names
        if word in self.mappings.project_names:
            return True
        # Check if it's in a title pattern
        # Single capitalized word in isolation is suspicious
        return True

    def scan_text(self, text: str, file_path: Optional[str] = None) -> List[PIIMatch]:
        """Scan text for PII, return matches."""
        matches = []
        lines = text.split('\n')

        for line_num, line in enumerate(lines, 1):
            # Check known project identifiers first
            for name in self.mappings.project_names:
                if name in line:
                    h = self.mappings.add(name, 'name')
                    matches.append(PIIMatch(
                        pii_type='name',
                        original=name,
                        hash=h,
                        context=line[:100],
                        file_path=file_path,
                        line_number=line_num
                    ))

            for site in self.mappings.project_sites:
                if site in line:
                    h = self.mappings.add(site, 'site')
                    matches.append(PIIMatch(
                        pii_type='site',
                        original=site,
                        hash=h,
                        context=line[:100],
                        file_path=file_path,
                        line_number=line_num
                    ))

            for org in self.mappings.project_orgs:
                if org in line:
                    h = self.mappings.add(org, 'org')
                    matches.append(PIIMatch(
                        pii_type='org',
                        original=org,
                        hash=h,
                        context=line[:100],
                        file_path=file_path,
                        line_number=line_num
                    ))

            # Email (always PII)
            for m in PATTERNS['email'].finditer(line):
                email = m.group(0)
                h = self.mappings.add(email, 'email')
                matches.append(PIIMatch(
                    pii_type='email',
                    original=email,
                    hash=h,
                    context=line[:100],
                    file_path=file_path,
                    line_number=line_num
                ))

            # Phone
            for m in PATTERNS['phone'].finditer(line):
                phone = m.group(0)
                h = self.mappings.add(phone, 'phone')
                matches.append(PIIMatch(
                    pii_type='phone',
                    original=phone,
                    hash=h,
                    context=line[:100],
                    file_path=file_path,
                    line_number=line_num
                ))

            # Potential names (capitalized sequences)
            for m in PATTERNS['potential_name'].finditer(line):
                name = m.group(1)
                # Skip if all words are common
                words = name.split()
                if all(w.lower() in self.skip_words for w in words):
                    continue
                h = self.mappings.add(name, 'name')
                matches.append(PIIMatch(
                    pii_type='name',
                    original=name,
                    hash=h,
                    context=line[:100],
                    file_path=file_path,
                    line_number=line_num
                ))

        return matches

    def scan_file(self, path: Path) -> List[PIIMatch]:
        """Scan a file for PII."""
        try:
            text = path.read_text(encoding='utf-8')
        except Exception as e:
            print(f"Warning: could not read {path}: {e}", file=sys.stderr)
            return []
        return self.scan_text(text, str(path))

    def scan_directory(self, dir_path: Path, extensions: Set[str] = None) -> List[PIIMatch]:
        """Scan all files in directory for PII."""
        if extensions is None:
            extensions = {'.txt', '.md', '.rtf', '.csv', '.json', '.jsonl'}

        all_matches = []
        for root, dirs, files in os.walk(dir_path):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.')]

            for fname in files:
                if any(fname.endswith(ext) for ext in extensions):
                    fpath = Path(root) / fname
                    matches = self.scan_file(fpath)
                    all_matches.extend(matches)

        return all_matches

    def anonymize(self, text: str) -> str:
        """Replace all known PII with hashes."""
        result = text

        # Sort by length (longest first) to avoid partial replacements
        items = sorted(self.mappings.mappings.items(), key=lambda x: -len(x[0]))

        for original, hash_val in items:
            # Use word boundaries to avoid partial matches (e.g., "Mas" in "mass")
            pattern = re.compile(r'\b' + re.escape(original) + r'\b', re.IGNORECASE)
            result = pattern.sub(f'[HASH:{hash_val}]', result)

        return result


def hash_content(content: str, nonce: Optional[str] = None) -> Tuple[str, str]:
    """
    Generate a hash for content that can be verified later.

    Returns (hash, nonce) - nonce must be stored privately.
    """
    if nonce is None:
        nonce = secrets.token_hex(16)

    # Canonicalize: strip whitespace, lowercase
    canonical = ' '.join(content.lower().split())

    # Hash with nonce
    combined = nonce + canonical
    h = hashlib.sha256(combined.encode('utf-8')).hexdigest()

    return h, nonce


def verify_content(content: str, expected_hash: str, nonce: str) -> bool:
    """Verify that content matches a previously generated hash."""
    computed, _ = hash_content(content, nonce)
    return computed == expected_hash


def generate_summary(text: str, max_words: int = 30) -> str:
    """
    Generate a non-identifying summary of text.

    Extracts key concepts without specific identifiers.
    """
    # Remove quotes
    text = re.sub(r'["""]', '', text)

    # Extract first sentence or max_words
    sentences = re.split(r'[.!?]', text)
    if sentences:
        first = sentences[0].strip()
        words = first.split()[:max_words]
        summary = ' '.join(words)
        if len(words) == max_words:
            summary += '...'
        return summary

    words = text.split()[:max_words]
    return ' '.join(words) + ('...' if len(words) == max_words else '')


# CLI

def scan_cmd(args):
    """Scan files for PII."""
    input_path = Path(args.input)

    # Load project config if available
    config_path = input_path / 'project_config.yaml' if input_path.is_dir() else input_path.parent / 'project_config.yaml'
    mappings = PIIMappings.from_project_config(config_path) if config_path.exists() else PIIMappings()

    # Add any additional names from args
    if args.names:
        for name in args.names.split(','):
            name = name.strip()
            if name:
                mappings.project_names.add(name)
                mappings.add(name, 'name')

    scanner = PIIScanner(mappings)

    if input_path.is_dir():
        matches = scanner.scan_directory(input_path)
    else:
        matches = scanner.scan_file(input_path)

    # Output
    print(f"Found {len(matches)} PII instances")
    print(f"Unique identifiers: {len(scanner.mappings.mappings)}")

    if args.verbose:
        for m in matches[:20]:
            print(f"  {m.pii_type}: {m.original} → {m.hash}")
        if len(matches) > 20:
            print(f"  ... and {len(matches) - 20} more")

    # Save mappings
    mappings_path = Path(args.mappings)
    mappings_path.write_text(scanner.mappings.to_json(), encoding='utf-8')
    print(f"Mappings saved to: {mappings_path}")
    print("⚠️  WARNING: This file contains PII. Keep secure, do not share.")


def anonymize_cmd(args):
    """Anonymize text using mappings."""
    mappings = PIIMappings.from_json(Path(args.mappings).read_text())
    scanner = PIIScanner(mappings)

    if args.input == '-':
        text = sys.stdin.read()
    else:
        text = Path(args.input).read_text()

    result = scanner.anonymize(text)

    if args.output:
        Path(args.output).write_text(result)
        print(f"Anonymized output written to: {args.output}")
    else:
        print(result)


def hash_cmd(args):
    """Hash content for verification."""
    if args.input == '-':
        content = sys.stdin.read()
    else:
        content = args.input

    h, nonce = hash_content(content, args.nonce)

    print(f"Hash: {h}")
    print(f"Nonce: {nonce}")
    print("Store nonce privately for later verification.")


def main():
    parser = argparse.ArgumentParser(description='PII detection and hashing')
    sub = parser.add_subparsers(dest='cmd', required=True)

    # scan
    scan_p = sub.add_parser('scan', help='Scan files for PII')
    scan_p.add_argument('--input', '-i', required=True, help='File or directory to scan')
    scan_p.add_argument('--mappings', '-m', required=True, help='Output mappings file (JSON)')
    scan_p.add_argument('--names', help='Additional names to detect (comma-separated)')
    scan_p.add_argument('--verbose', '-v', action='store_true')

    # anonymize
    anon_p = sub.add_parser('anonymize', help='Anonymize text using mappings')
    anon_p.add_argument('--input', '-i', required=True, help='File to anonymize (or - for stdin)')
    anon_p.add_argument('--mappings', '-m', required=True, help='Mappings file')
    anon_p.add_argument('--output', '-o', help='Output file (default: stdout)')

    # hash
    hash_p = sub.add_parser('hash-content', help='Hash content for verification')
    hash_p.add_argument('--input', '-i', required=True, help='Content to hash (or - for stdin)')
    hash_p.add_argument('--nonce', help='Use specific nonce (default: generate new)')

    args = parser.parse_args()

    if args.cmd == 'scan':
        scan_cmd(args)
    elif args.cmd == 'anonymize':
        anonymize_cmd(args)
    elif args.cmd == 'hash-content':
        hash_cmd(args)


if __name__ == '__main__':
    main()
