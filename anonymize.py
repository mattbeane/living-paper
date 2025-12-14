#!/usr/bin/env python3
"""
anonymize.py - k-anonymity enforcement for evidence metadata

Ensures that metadata combinations can't re-identify individuals by:
1. Binning continuous variables (tenure → tenure_bin)
2. Generalizing categorical variables (specific_role → role_category)
3. Suppressing cells with fewer than k instances

Usage:
    python anonymize.py check --input <metadata.csv> --k 3
    python anonymize.py apply --input <metadata.csv> --output <safe.csv> --k 3
    python anonymize.py report --input <metadata.csv> --k 3
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Default k value (minimum instances per cell)
DEFAULT_K = 3


@dataclass
class AnonymizationConfig:
    """Configuration for anonymization rules."""
    k: int = DEFAULT_K

    # Binning rules for continuous variables
    # variable_name: [(threshold, bin_label), ...]
    binning_rules: Dict[str, List[Tuple[float, str]]] = field(default_factory=lambda: {
        'tenure_years': [
            (1, '<1 year'),
            (3, '1-3 years'),
            (5, '3-5 years'),
            (10, '5-10 years'),
            (float('inf'), '10+ years'),
        ],
        'age': [
            (25, '<25'),
            (35, '25-35'),
            (45, '35-45'),
            (55, '45-55'),
            (float('inf'), '55+'),
        ],
    })

    # Generalization rules for categorical variables
    # original_value: generalized_value
    generalization_rules: Dict[str, Dict[str, str]] = field(default_factory=lambda: {
        'role': {
            'supervisor': 'management',
            'manager': 'management',
            'director': 'management',
            'vp': 'management',
            'associate': 'frontline',
            'worker': 'frontline',
            'picker': 'frontline',
            'packer': 'frontline',
            'sorter': 'frontline',
            'lead': 'frontline',
            'engineer': 'technical',
            'analyst': 'technical',
            'developer': 'technical',
        },
        'site': {
            # Site-specific generalizations go here
            # Will be populated from project config
        }
    })

    # Quasi-identifiers (columns that together could identify someone)
    quasi_identifiers: List[str] = field(default_factory=lambda: [
        'role_bin', 'tenure_bin', 'site_bin', 'shift', 'department'
    ])

    # Columns to suppress entirely (never include in output)
    suppress_columns: List[str] = field(default_factory=lambda: [
        'name', 'email', 'phone', 'address', 'employee_id', 'ssn'
    ])


@dataclass
class AnonymizationResult:
    """Result of anonymization check."""
    is_safe: bool
    k_value: int
    violations: List[Dict[str, Any]]  # Cells below k threshold
    suppressed_rows: int
    total_rows: int
    unique_combinations: int


class KAnonymizer:
    """Applies k-anonymity to tabular data."""

    def __init__(self, config: Optional[AnonymizationConfig] = None):
        self.config = config or AnonymizationConfig()

    def bin_value(self, value: Any, variable: str) -> str:
        """Bin a continuous value according to rules."""
        if variable not in self.config.binning_rules:
            return str(value)

        try:
            num = float(value)
        except (ValueError, TypeError):
            return str(value)

        for threshold, label in self.config.binning_rules[variable]:
            if num < threshold:
                return label
        return str(value)

    def generalize_value(self, value: Any, variable: str) -> str:
        """Generalize a categorical value."""
        if variable not in self.config.generalization_rules:
            return str(value).lower()

        rules = self.config.generalization_rules[variable]
        val_lower = str(value).lower()
        return rules.get(val_lower, val_lower)

    def get_equivalence_class(self, row: Dict[str, str]) -> Tuple[str, ...]:
        """Get the equivalence class (quasi-identifier combination) for a row."""
        values = []
        for qi in self.config.quasi_identifiers:
            if qi in row:
                values.append(str(row[qi]))
            else:
                values.append('')
        return tuple(values)

    def check_k_anonymity(self, rows: List[Dict[str, str]]) -> AnonymizationResult:
        """Check if data satisfies k-anonymity."""
        # Count equivalence classes
        eq_classes = Counter()
        for row in rows:
            eq_class = self.get_equivalence_class(row)
            eq_classes[eq_class] += 1

        # Find violations
        violations = []
        for eq_class, count in eq_classes.items():
            if count < self.config.k:
                violations.append({
                    'equivalence_class': dict(zip(self.config.quasi_identifiers, eq_class)),
                    'count': count,
                    'required': self.config.k,
                    'deficit': self.config.k - count
                })

        # Count affected rows
        suppressed = sum(v['count'] for v in violations)

        return AnonymizationResult(
            is_safe=len(violations) == 0,
            k_value=self.config.k,
            violations=violations,
            suppressed_rows=suppressed,
            total_rows=len(rows),
            unique_combinations=len(eq_classes)
        )

    def apply_anonymization(self, rows: List[Dict[str, str]],
                            suppress_violations: bool = True) -> List[Dict[str, str]]:
        """
        Apply anonymization to rows.

        1. Remove suppressed columns
        2. Bin continuous variables
        3. Generalize categorical variables
        4. Optionally suppress rows in small equivalence classes
        """
        result = []

        # First pass: transform all rows
        transformed = []
        for row in rows:
            new_row = {}
            for key, value in row.items():
                # Skip suppressed columns
                if key.lower() in [c.lower() for c in self.config.suppress_columns]:
                    continue

                # Apply binning if applicable
                if key in self.config.binning_rules:
                    new_row[f"{key}_bin"] = self.bin_value(value, key)
                # Apply generalization if applicable
                elif key in self.config.generalization_rules:
                    new_row[f"{key}_bin"] = self.generalize_value(value, key)
                else:
                    new_row[key] = value

            transformed.append(new_row)

        if not suppress_violations:
            return transformed

        # Second pass: identify and suppress small equivalence classes
        eq_classes = Counter()
        for row in transformed:
            eq_class = self.get_equivalence_class(row)
            eq_classes[eq_class] += 1

        # Keep only rows in large enough equivalence classes
        for row in transformed:
            eq_class = self.get_equivalence_class(row)
            if eq_classes[eq_class] >= self.config.k:
                result.append(row)

        return result

    def generate_report(self, rows: List[Dict[str, str]]) -> str:
        """Generate a k-anonymity report."""
        check = self.check_k_anonymity(rows)

        lines = [
            "# K-Anonymity Report",
            "",
            f"**K value**: {check.k_value}",
            f"**Total rows**: {check.total_rows}",
            f"**Unique combinations**: {check.unique_combinations}",
            f"**Status**: {'✓ SAFE' if check.is_safe else '✗ VIOLATIONS FOUND'}",
            "",
        ]

        if check.violations:
            lines.append("## Violations")
            lines.append("")
            lines.append(f"Found {len(check.violations)} equivalence classes below k={check.k_value}:")
            lines.append("")

            for v in check.violations[:20]:  # Show first 20
                eq = v['equivalence_class']
                eq_str = ', '.join(f"{k}={v}" for k, v in eq.items() if v)
                lines.append(f"- **{v['count']}** instances: {eq_str}")

            if len(check.violations) > 20:
                lines.append(f"- ... and {len(check.violations) - 20} more")

            lines.append("")
            lines.append(f"**Rows to suppress**: {check.suppressed_rows} ({100*check.suppressed_rows/check.total_rows:.1f}%)")
        else:
            lines.append("## Summary")
            lines.append("")
            lines.append("All equivalence classes have at least k members. Data is safe to share.")

        # Recommendations
        lines.append("")
        lines.append("## Recommendations")
        lines.append("")

        if check.suppressed_rows > check.total_rows * 0.2:
            lines.append("- Consider increasing generalization to reduce suppression")
            lines.append("- Current suppression rate is high (>20%)")
        elif check.violations:
            lines.append("- Suppress the identified rows before sharing")
            lines.append("- Or: increase generalization for quasi-identifiers")
        else:
            lines.append("- Data meets k-anonymity requirements")
            lines.append("- Safe to include in PUBLIC tier exports")

        return "\n".join(lines)


def load_csv(path: Path) -> List[Dict[str, str]]:
    """Load CSV file as list of dicts."""
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def save_csv(rows: List[Dict[str, str]], path: Path) -> None:
    """Save list of dicts to CSV."""
    if not rows:
        return

    fieldnames = list(rows[0].keys())
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# CLI

def check_cmd(args):
    """Check k-anonymity of data."""
    config = AnonymizationConfig(k=args.k)
    anonymizer = KAnonymizer(config)

    rows = load_csv(Path(args.input))
    result = anonymizer.check_k_anonymity(rows)

    print(f"K-anonymity check (k={args.k}):")
    print(f"  Total rows: {result.total_rows}")
    print(f"  Unique combinations: {result.unique_combinations}")

    if result.is_safe:
        print(f"  Status: ✓ SAFE")
    else:
        print(f"  Status: ✗ {len(result.violations)} violations")
        print(f"  Rows to suppress: {result.suppressed_rows}")

        if args.verbose:
            for v in result.violations[:10]:
                eq = v['equivalence_class']
                eq_str = ', '.join(f"{k}={v}" for k, v in eq.items() if v)
                print(f"    - {v['count']} instances: {eq_str}")


def apply_cmd(args):
    """Apply anonymization to data."""
    config = AnonymizationConfig(k=args.k)
    anonymizer = KAnonymizer(config)

    rows = load_csv(Path(args.input))
    safe_rows = anonymizer.apply_anonymization(rows, suppress_violations=not args.keep_violations)

    save_csv(safe_rows, Path(args.output))

    print(f"Anonymization applied:")
    print(f"  Input rows: {len(rows)}")
    print(f"  Output rows: {len(safe_rows)}")
    print(f"  Suppressed: {len(rows) - len(safe_rows)}")
    print(f"  Output: {args.output}")


def report_cmd(args):
    """Generate k-anonymity report."""
    config = AnonymizationConfig(k=args.k)
    anonymizer = KAnonymizer(config)

    rows = load_csv(Path(args.input))
    report = anonymizer.generate_report(rows)

    if args.output:
        Path(args.output).write_text(report)
        print(f"Report saved to: {args.output}")
    else:
        print(report)


def main():
    parser = argparse.ArgumentParser(description='K-anonymity enforcement')
    sub = parser.add_subparsers(dest='cmd', required=True)

    # check
    check_p = sub.add_parser('check', help='Check k-anonymity')
    check_p.add_argument('--input', '-i', required=True, help='Input CSV')
    check_p.add_argument('--k', type=int, default=DEFAULT_K, help=f'K value (default: {DEFAULT_K})')
    check_p.add_argument('--verbose', '-v', action='store_true')

    # apply
    apply_p = sub.add_parser('apply', help='Apply anonymization')
    apply_p.add_argument('--input', '-i', required=True, help='Input CSV')
    apply_p.add_argument('--output', '-o', required=True, help='Output CSV')
    apply_p.add_argument('--k', type=int, default=DEFAULT_K, help=f'K value (default: {DEFAULT_K})')
    apply_p.add_argument('--keep-violations', action='store_true', help='Keep rows that violate k-anonymity')

    # report
    report_p = sub.add_parser('report', help='Generate report')
    report_p.add_argument('--input', '-i', required=True, help='Input CSV')
    report_p.add_argument('--output', '-o', help='Output file (default: stdout)')
    report_p.add_argument('--k', type=int, default=DEFAULT_K, help=f'K value (default: {DEFAULT_K})')

    args = parser.parse_args()

    if args.cmd == 'check':
        check_cmd(args)
    elif args.cmd == 'apply':
        apply_cmd(args)
    elif args.cmd == 'report':
        report_cmd(args)


if __name__ == '__main__':
    main()
