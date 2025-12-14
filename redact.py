#!/usr/bin/env python3
"""
redact.py - Entity redaction for claim/evidence text fields

Handles PII that k-anonymity cannot address: vendor names, site names,
project names, and other identifying entities in free text.

Usage:
    # Check what would be redacted
    python redact.py check --input claims.jsonl --entities entities.yaml

    # Apply redaction to file
    python redact.py apply --input claims.jsonl --output claims_redacted.jsonl --entities entities.yaml

    # Redact a single string (for API use)
    python redact.py text "PM met with Kindred engineers" --entities entities.yaml

The entities.yaml format:
    vendors:
      Kindred: "Vendor A"
      Vicarious: "Vendor B"
    sites:
      Bloomington: "Site Alpha"
    patterns:
      - pattern: "\\$\\d+K"
        replacement: "[AMOUNT]"
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


@dataclass
class RedactionStats:
    """Track what was redacted."""
    total_redactions: int = 0
    by_category: Dict[str, int] = field(default_factory=dict)
    by_entity: Dict[str, int] = field(default_factory=dict)
    samples: List[Tuple[str, str]] = field(default_factory=list)  # (original, redacted) pairs


class EntityRedactor:
    """Redacts identifying entities from text."""

    def __init__(self, entities_path: Optional[Path] = None, entities_dict: Optional[Dict] = None):
        """
        Initialize with either a path to entities.yaml or a dict directly.
        """
        self.entities: Dict[str, Dict[str, str]] = {}
        self.patterns: List[Dict[str, str]] = []

        if entities_dict:
            self._load_from_dict(entities_dict)
        elif entities_path:
            self._load_from_file(entities_path)

    def _load_from_file(self, path: Path) -> None:
        """Load entity mappings from YAML or JSON file."""
        if not isinstance(path, Path):
            path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Entities file not found: {path}")

        content = path.read_text(encoding='utf-8')

        if path.suffix in ('.yaml', '.yml'):
            if not HAS_YAML:
                raise ImportError("PyYAML required for .yaml files. Install with: pip install pyyaml")
            data = yaml.safe_load(content)
        else:
            data = json.loads(content)

        self._load_from_dict(data)

    def _load_from_dict(self, data: Dict) -> None:
        """Load entity mappings from a dictionary."""
        # Extract patterns if present
        if 'patterns' in data:
            self.patterns = data.pop('patterns') or []

        # Everything else is category -> {original: replacement}
        for category, mappings in data.items():
            if isinstance(mappings, dict):
                self.entities[category] = mappings
            elif isinstance(mappings, list):
                # Handle list format: [{original: X, replacement: Y}, ...]
                self.entities[category] = {}
                for item in mappings:
                    if isinstance(item, dict) and 'original' in item and 'replacement' in item:
                        self.entities[category][item['original']] = item['replacement']

    def redact(self, text: str, stats: Optional[RedactionStats] = None) -> str:
        """
        Redact all known entities from text.

        Returns the redacted text. If stats is provided, updates it with
        information about what was redacted.
        """
        if not text:
            return text

        original_text = text

        # Apply entity replacements (case-insensitive, word-boundary aware)
        for category, mappings in self.entities.items():
            for original, replacement in mappings.items():
                # Match word boundary, entity, and optional possessive suffix ('s, 's)
                # This catches: Kindred, Kindred's, Kindred's, KINDRED, etc.
                pattern = rf"\b{re.escape(original)}(?:'s|'s)?\b"
                matches = re.findall(pattern, text, flags=re.IGNORECASE)

                if matches and stats:
                    stats.total_redactions += len(matches)
                    stats.by_category[category] = stats.by_category.get(category, 0) + len(matches)
                    stats.by_entity[original] = stats.by_entity.get(original, 0) + len(matches)

                # Replace with possessive form if original was possessive
                def replace_with_possessive(m):
                    matched = m.group(0)
                    if matched.endswith("'s") or matched.endswith("'s"):
                        return replacement + "'s"
                    return replacement

                text = re.sub(pattern, replace_with_possessive, text, flags=re.IGNORECASE)

        # Apply regex patterns
        for p in self.patterns:
            pattern = p.get('pattern', '')
            replacement = p.get('replacement', '[REDACTED]')

            if pattern:
                matches = re.findall(pattern, text)
                if matches and stats:
                    stats.total_redactions += len(matches)
                    stats.by_category['patterns'] = stats.by_category.get('patterns', 0) + len(matches)

                text = re.sub(pattern, replacement, text)

        # Track sample if changed
        if stats and text != original_text:
            if len(stats.samples) < 10:  # Keep first 10 samples
                stats.samples.append((original_text, text))

        return text

    def redact_jsonl_record(self, record: Dict[str, Any],
                           text_fields: List[str] = None,
                           stats: Optional[RedactionStats] = None) -> Dict[str, Any]:
        """
        Redact text fields in a JSONL record.

        Default text fields: 'text', 'summary', 'note', 'analytic_note', 'claim_text'
        """
        if text_fields is None:
            text_fields = ['text', 'summary', 'note', 'analytic_note', 'claim_text', 'audit_notes']

        result = record.copy()

        for field in text_fields:
            if field in result and isinstance(result[field], str):
                result[field] = self.redact(result[field], stats)

        # Handle nested meta dict if present
        if 'meta' in result and isinstance(result['meta'], dict):
            for key, value in result['meta'].items():
                if isinstance(value, str):
                    result['meta'][key] = self.redact(value, stats)

        return result

    def generate_report(self, stats: RedactionStats) -> str:
        """Generate a human-readable redaction report."""
        lines = [
            "# Redaction Report",
            "",
            f"**Total redactions:** {stats.total_redactions}",
            "",
        ]

        if stats.by_category:
            lines.append("## By Category")
            lines.append("")
            for cat, count in sorted(stats.by_category.items(), key=lambda x: -x[1]):
                lines.append(f"- {cat}: {count}")
            lines.append("")

        if stats.by_entity:
            lines.append("## By Entity")
            lines.append("")
            for entity, count in sorted(stats.by_entity.items(), key=lambda x: -x[1]):
                lines.append(f"- `{entity}`: {count}")
            lines.append("")

        if stats.samples:
            lines.append("## Sample Redactions")
            lines.append("")
            for orig, redacted in stats.samples[:5]:
                lines.append(f"**Before:** {orig[:100]}{'...' if len(orig) > 100 else ''}")
                lines.append(f"**After:** {redacted[:100]}{'...' if len(redacted) > 100 else ''}")
                lines.append("")

        return "\n".join(lines)


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Load JSONL file."""
    records = []
    with path.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def save_jsonl(records: List[Dict[str, Any]], path: Path) -> None:
    """Save records to JSONL file."""
    with path.open('w', encoding='utf-8') as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')


# CLI commands

def check_cmd(args: argparse.Namespace) -> None:
    """Check what would be redacted without modifying files."""
    redactor = EntityRedactor(entities_path=Path(args.entities))
    stats = RedactionStats()

    input_path = Path(args.input)
    records = load_jsonl(input_path)

    for record in records:
        redactor.redact_jsonl_record(record, stats=stats)

    print(redactor.generate_report(stats))

    if stats.total_redactions > 0:
        print(f"\n[redact] Would redact {stats.total_redactions} entities in {len(records)} records")
    else:
        print(f"\n[redact] No entities to redact in {len(records)} records")


def apply_cmd(args: argparse.Namespace) -> None:
    """Apply redaction to a JSONL file."""
    redactor = EntityRedactor(entities_path=Path(args.entities))
    stats = RedactionStats()

    input_path = Path(args.input)
    output_path = Path(args.output)

    records = load_jsonl(input_path)
    redacted_records = [redactor.redact_jsonl_record(r, stats=stats) for r in records]

    save_jsonl(redacted_records, output_path)

    print(f"[redact] Redacted {stats.total_redactions} entities across {len(records)} records")
    print(f"[redact] Output: {output_path}")

    if args.verbose:
        print("\n" + redactor.generate_report(stats))


def text_cmd(args: argparse.Namespace) -> None:
    """Redact a single text string."""
    redactor = EntityRedactor(entities_path=Path(args.entities))
    result = redactor.redact(args.text)
    print(result)


def main() -> None:
    parser = argparse.ArgumentParser(description='Entity redaction for Living Paper')
    sub = parser.add_subparsers(dest='cmd', required=True)

    # check
    check_p = sub.add_parser('check', help='Check what would be redacted')
    check_p.add_argument('--input', '-i', required=True, help='Input JSONL file')
    check_p.add_argument('--entities', '-e', required=True, help='Entities YAML/JSON file')

    # apply
    apply_p = sub.add_parser('apply', help='Apply redaction')
    apply_p.add_argument('--input', '-i', required=True, help='Input JSONL file')
    apply_p.add_argument('--output', '-o', required=True, help='Output JSONL file')
    apply_p.add_argument('--entities', '-e', required=True, help='Entities YAML/JSON file')
    apply_p.add_argument('--verbose', '-v', action='store_true')

    # text
    text_p = sub.add_parser('text', help='Redact a single text string')
    text_p.add_argument('text', help='Text to redact')
    text_p.add_argument('--entities', '-e', required=True, help='Entities YAML/JSON file')

    args = parser.parse_args()

    if args.cmd == 'check':
        check_cmd(args)
    elif args.cmd == 'apply':
        apply_cmd(args)
    elif args.cmd == 'text':
        text_cmd(args)


if __name__ == '__main__':
    main()
