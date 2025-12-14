# Release Notes

## v0.5.0 (2024-12-14)

### New Features

- **Static HTML Reviewer**: Generate self-contained HTML files reviewers can open in any browser—no server needed
- **Reviewer Packages**: Create complete folders with HTML, README, and double-click launchers (Mac/Windows)
- **Prevalence Metadata**: Track informant coverage, contradicting evidence counts, and saturation notes
- **Contradiction Badges**: Visual highlighting of contradicting evidence in the reviewer interface
- **Entity Redaction**: Built-in tools to anonymize vendor names, sites, and other PII before sharing

### Commands

```bash
# Generate reviewer package
python3 lp.py export-package --paper your-paper-id --out ./reviewer_folder

# Redaction workflow
python3 lp.py redact check --input claims.jsonl --entities entities.yaml
python3 lp.py redact apply --input claims.jsonl --output claims_redacted.jsonl --entities entities.yaml
```

### Installation

```bash
git clone https://github.com/mattbeane/living-paper.git
cd living-paper
python3 lp.py init
```

Requires Python 3.10+. No external dependencies.

---

## Previous Versions

### v0.4.0

- Initial public release
- Core claim-evidence linking
- `lint` and `prereview` commands
- Basic export functionality
