# For Authors: Complete Workflow Guide

This guide walks you through preparing your qualitative research for Living Paper verification, from raw data to reviewer-ready packages.

## Overview

The author workflow has four phases:

1. **Prepare** — Document your claims, evidence, and links
2. **Redact** — Anonymize identifying information
3. **Ingest** — Load data into Living Paper
4. **Export** — Generate verification packages for reviewers

---

## Phase 1: Prepare Your Data

Living Paper expects three input files:

### Claims File (`claims.jsonl`)

One JSON object per line, each representing a substantive claim in your paper:

```json
{"claim_id": "C1", "paper_id": "my-paper", "claim_type": "empirical", "text": "Workers adapted to automation by developing new expertise categories."}
{"claim_id": "C2", "paper_id": "my-paper", "claim_type": "theoretical", "text": "Shadow learning accelerates when formal training is unavailable."}
```

**Required fields:**
- `claim_id` — Unique identifier (e.g., C1, C2)
- `paper_id` — Groups claims by paper
- `claim_type` — One of: `empirical`, `theoretical`, `methodological`, `definitional`, `boundary_condition`
- `text` — The claim itself

**Optional fields (recommended):**
- `confidence` — 0.0 to 1.0 (default: 0.5)
- `informant_coverage` — e.g., "12/47 informants" or "widespread"
- `saturation_note` — e.g., "Pattern consistent across all sites"
- `prevalence_basis` — One of: `representative`, `illustrative`, `singular`, `aggregate`

### Evidence File (`evidence.jsonl`)

One JSON object per line, each representing a piece of evidence:

```json
{"evidence_id": "E1", "paper_id": "my-paper", "evidence_type": "quote", "summary": "Senior operator describes learning new diagnostic skills by watching automation failures", "sensitivity_tier": "PUBLIC", "meta": {"informant_role_bin": "operator", "site_bin": "A"}}
{"evidence_id": "E2", "paper_id": "my-paper", "evidence_type": "observation", "summary": "Researcher observed workers taking notes during robot downtime", "sensitivity_tier": "PUBLIC"}
```

**Required fields:**
- `evidence_id` — Unique identifier
- `paper_id` — Must match claim paper_id
- `evidence_type` — e.g., `quote`, `observation`, `statistic`, `document`
- `summary` — Brief description (NOT the raw quote—summarize it)
- `sensitivity_tier` — `PUBLIC`, `CONTROLLED`, or `WITNESS_ONLY`

**Optional:**
- `meta` — Object with additional metadata (role, tenure, site bins, etc.)

### Links File (`links.csv`)

CSV connecting claims to evidence:

```csv
claim_id,evidence_id,relation,weight,note
C1,E1,supports,central,"Direct testimony about skill development"
C1,E2,supports,supporting,"Corroborating behavioral observation"
C2,E1,illustrates,supporting,"Example of shadow learning in action"
```

**Columns:**
- `claim_id`, `evidence_id` — Must exist in respective files
- `relation` — One of: `supports`, `challenges`, `illustrates`, `qualifies`, `necessitates`
- `weight` — One of: `central`, `supporting`, `peripheral`
- `note` — Optional explanation of the link

---

## Phase 2: Redact Identifying Information

Before sharing verification packages, you likely need to anonymize vendor names, site locations, project names, and other identifying information.

### Step 1: Create Your Entities File

Copy the example and customize it:

```bash
cp entities_example.yaml entities.yaml
```

Edit `entities.yaml` with your specific mappings:

```yaml
# Vendor/company names
vendors:
  Kindred: "Vendor A"
  Vicarious: "Vendor B"
  GreyOrange: "Vendor C"

# Site/facility names
sites:
  Bloomington: "Site Alpha"
  Commerce: "Site Beta"
  Hebron: "Site Gamma"

# Internal project names
projects:
  ACHIEVE: "Project-A"
  PHOENIX: "Project-B"

# Regex patterns for dynamic redaction
patterns:
  - pattern: "\\$\\d+K"
    replacement: "[AMOUNT]"
```

### Step 2: Preview Redactions

Check what would be redacted before applying:

```bash
python3 lp.py redact check --input claims.jsonl --entities entities.yaml
```

This shows:
- Total redaction count
- Redactions by category (vendors, sites, etc.)
- Sample before/after comparisons

### Step 3: Apply Redactions

Option A — Redact files separately, then ingest:

```bash
python3 lp.py redact apply --input claims.jsonl --output claims_redacted.jsonl --entities entities.yaml
python3 lp.py redact apply --input evidence.jsonl --output evidence_redacted.jsonl --entities entities.yaml

python3 lp.py ingest --claims claims_redacted.jsonl --evidence evidence_redacted.jsonl --links links.csv
```

Option B — Redact automatically during ingest (simpler):

```bash
python3 lp.py ingest --claims claims.jsonl --evidence evidence.jsonl --links links.csv --entities entities.yaml
```

Both approaches produce the same result: a database with redacted text.

---

## Phase 3: Ingest and Validate

### Initialize the Database

```bash
python3 lp.py init
```

Creates:
- `analysis/living_paper/lp_public.sqlite` — Shareable metadata
- `analysis/living_paper/lp_private.sqlite` — Protected pointers (gitignore this)

### Ingest Your Data

```bash
python3 lp.py ingest --claims claims.jsonl --evidence evidence.jsonl --links links.csv --entities entities.yaml
```

### Run Validation

```bash
python3 lp.py lint
```

Checks:
- Every claim has at least one linked evidence item
- All links point to existing claims/evidence
- Warns about orphaned evidence (not linked to any claim)

### Generate Pre-Review Report

```bash
python3 lp.py prereview --out ./prereview_report.md
```

This identifies **contested claims** — those with:
- Challenging evidence
- Low confidence
- More qualifications than support

Address these before submission. The report includes adjudication prompts to help you resolve contradictions.

---

## Phase 4: Export for Reviewers

### Option A: Static HTML Package (Recommended)

Generate a self-contained folder reviewers can use offline:

```bash
python3 lp.py export-package --paper my-paper --out ./reviewer_package
```

Creates:
```
reviewer_package/
  review.html           # The verification interface
  README.txt            # Instructions for reviewers
  Open Review.command   # Mac double-click launcher
  Open Review.bat       # Windows launcher
```

**Share this folder with reviewers.** They double-click to open, no installation needed.

### Option B: HTML File Only

If you just need the HTML:

```bash
python3 lp.py export-html --paper my-paper --out ./review.html
```

### Option C: JSON/Markdown Export

For programmatic access or integration with other tools:

```bash
python3 lp.py export --out ./verification_export
python3 lp.py verify-export --out ./verification_package
```

---

## What Reviewers See

When reviewers open the verification interface, they see:

1. **Claim cards** with:
   - Claim ID and type
   - Support status badge (supported/contested/partial)
   - Prevalence metadata (informant coverage, saturation notes)
   - Confidence level

2. **Evidence items** for each claim:
   - Relation type (supports/challenges/qualifies)
   - Weight (central/supporting/peripheral)
   - Summary text (redacted)
   - Contradiction badges where applicable

3. **Verification controls**:
   - Mark each link as Verified / Author Only / Not Verified
   - Add reviewer notes
   - Generate markdown report

**Reviewers never see your raw transcripts.** They see structure, summaries, and metadata that let them evaluate your evidence without accessing protected data.

---

## Best Practices

### Documenting Claims

- Be specific. "Workers learned informally" is vague; "Workers developed diagnostic expertise through observation of automation failures" is verifiable.
- Include confidence levels honestly. Low confidence with good evidence is better than false certainty.
- Document prevalence. "12/47 informants mentioned this" is more convincing than "many informants said."

### Linking Evidence

- Central evidence should be your strongest support
- Include challenging evidence—it makes your paper stronger
- Link the same evidence to multiple claims if appropriate

### Redaction

- Be thorough. Search your text for all variations (Kindred, Kindred's, KINDRED)
- Test with `redact check` before applying
- Keep your entities file updated as you find new identifying terms

### Before Submission

- Run `lint` to catch structural issues
- Run `prereview` to surface contested claims
- Address contradictions explicitly in your paper
- Generate a fresh package and test it yourself before sending to reviewers

---

## Troubleshooting

**"claims.jsonl missing 'claim_id'"**
- Each line must be valid JSON with required fields
- Check for trailing commas or missing quotes

**"Found broken link(s)"**
- A link references a claim_id or evidence_id that doesn't exist
- Check for typos in IDs

**"X claim(s) have zero linked evidence"**
- Every claim must have at least one evidence link
- Add links or remove unsupported claims

**Redaction not working**
- Check your entities.yaml syntax (YAML is whitespace-sensitive)
- Use `redact check` to see what's being matched
- Patterns are case-insensitive by default

---

## Questions?

Contact Matt Beane (mattbeane@ucsb.edu) or open an issue on GitHub.
