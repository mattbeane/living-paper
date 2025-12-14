# Living Paper

**Bidirectional claim-evidence traceability for qualitative research.**

Living Paper is a local-first tool that maintains verifiable links between the claims you make in papers and the evidence supporting them—while keeping sensitive data protected. It enables:

- **Pre-review**: Surface contested claims and weak evidence *before* submission
- **Verification**: Let reviewers verify claims without exposing protected transcripts
- **Audit trail**: Track how claims evolve as you engage with your data

## Why This Matters

Academic papers are frozen artifacts. Once published, the journey from data to claim is invisible. Living Paper makes that relationship explicit, auditable, and—where possible—verifiable.

For qualitative research specifically, this addresses the persistent critique that findings are unfalsifiable because evidence is inaccessible. Living Papers create infrastructure for verification that doesn't currently exist.

## Quick Start

```bash
# Clone and enter the repo
git clone https://github.com/mattbeane/living-paper.git
cd living-paper

# Initialize in your project
python3 lp.py init

# Ingest your claims, evidence, and links
python3 lp.py ingest \
  --claims path/to/claims.jsonl \
  --evidence path/to/evidence.jsonl \
  --links path/to/links.csv

# Check for traceability issues
python3 lp.py lint

# Generate pre-review report (surface contested claims)
python3 lp.py prereview

# Export verification package
python3 lp.py export --out ./exports/PUBLIC
```

## Core Concepts

### Claims
Every substantive claim in your paper is a discrete, addressable object:
```json
{
  "claim_id": "CLM-001",
  "paper_id": "PAPER-001",
  "claim_type": "mechanism",
  "text": "Managers used uncertainty talk to justify process experimentation.",
  "status": "draft",
  "verification_mode": "public_provenance"
}
```

### Evidence
Data supporting claims, with appropriate sensitivity tiers:
```json
{
  "evidence_id": "EVD-001",
  "paper_id": "PAPER-001",
  "evidence_type": "quote",
  "summary": "Ops manager describes not knowing the automation timeline.",
  "sensitivity_tier": "PUBLIC",
  "meta": {"interview_id": "INT_023", "informant_role_bin": "operations_manager"}
}
```

### Links
Typed, weighted connections between claims and evidence:
- **Relation**: supports, challenges, qualifies, illustrates, necessitates
- **Weight**: central, supporting, peripheral

## Pre-Review Workflow

The `prereview` command surfaces claims that need attention before submission:

1. **Contested claims**: Evidence cuts both ways
2. **Weak claims**: Few supporting links, low confidence
3. **Challenged claims**: Direct contradictions in the data

For each flagged claim, the system generates adjudication prompts appropriate to the claim type:

- **Empirical/Quant claims**: Can only be challenged by other quant data
- **Mechanism claims**: Use behavioral patterns to rule out alternatives

This isn't p-hacking—your quantitative data is fixed. It's principled mechanism refinement with an audit trail.

See `docs/PREREVIEW.md` for the full methodology.

## Three-Tier Access Control

| Tier | Contains | Who Sees It |
|------|----------|-------------|
| PUBLIC | Claim text, evidence summaries, link metadata | Anyone |
| CONTROLLED | Anonymized quotes with binned demographics | Approved reviewers |
| WITNESS_ONLY | Raw transcripts with hashed identifiers | Author only |

## Input Formats

### claims.jsonl
One JSON object per line:
- `claim_id` (string, required)
- `paper_id` (string, required)
- `claim_type`: mechanism, descriptive, boundary_condition, measurement, process
- `text` (string, required)
- `status`: draft, verified, superseded, retracted
- `verification_mode`: public_provenance, controlled_access, witness_only

### evidence.jsonl
One JSON object per line:
- `evidence_id` (string, required)
- `paper_id` (string, required)
- `evidence_type`: quote, fieldnote, observation, quant_output, other
- `summary` (string, required) — non-identifying description
- `sensitivity_tier`: PUBLIC, CONTROLLED, WITNESS_ONLY
- `meta` (object) — binned metadata (interview_id, role_bin, tenure_bin, site_bin)

### links.csv
Columns: `claim_id, evidence_id, relation, weight, note`

## Git Hygiene

Add to your `.gitignore`:
```
lp_private.sqlite
exports/WITNESS_ONLY/
exports/CONTROLLED/
```

## Quant/Qual Hierarchy

A critical methodological principle embedded in Living Paper:

> **Quantitative findings are ground truth.** Qualitative data can help explain *why* patterns exist, but cannot refute what the numbers show.

When a manager says "there was a mass exodus" but your retention data shows 94% stayed, the manager's statement is *evidence that their mental model is wrong*—not a challenge to the retention finding.

This hierarchy is enforced in pre-review adjudication prompts.

## Related Projects

- **[paper-mining-agents](https://github.com/mattbeane/paper-mining-agents)**: AI-assisted paper writing workflows that can generate living paper artifacts

## Requirements

- Python 3.10+
- No external dependencies (uses stdlib sqlite3, json, csv)

## Status

**v0.1** — Local-first implementation with:
- Dual SQLite stores (public metadata + private pointers)
- CLI for init, ingest, lint, export, prereview
- Three-tier access control
- Pre-review workflow

See `docs/LIVING_PAPER_SPEC.md` for the full vision through v1.0.

## Author

Matt Beane
