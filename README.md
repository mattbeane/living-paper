# Living Paper

**Make your qualitative research verifiable—without exposing your data.**

---

## The Problem You Know

A reviewer writes:

> "How do I know your informants actually said this? The quotes are compelling, but I have no way to verify they support your claims."

You can't share the transcripts—IRB won't allow it. You can't invite the reviewer into your data—there's no infrastructure for that. So you write a longer methods section, add more quotes, and hope they trust you.

They often don't. And honestly? They shouldn't have to.

---

## What Living Paper Does

Living Paper creates a **verification layer** between your claims and your protected data.

For each claim in your paper, you document:
- What evidence supports it (quotes, observations, statistics)
- What evidence challenges it (yes, really—this makes your paper stronger)
- How confident you are, and why

The result is a **verification package** you can share with reviewers. They see:
- Every claim, with its supporting and challenging evidence summarized
- Metadata about sources (anonymized role, tenure, site—whatever your IRB allows)
- A health indicator: Is this claim well-supported? Contested? Weak?

They *don't* see your raw transcripts. But they can verify that evidence exists and that you've engaged honestly with contradictions in your data.

---

## What This Gives You

**Before submission:**
- Surface contested claims before reviewers do
- Strengthen weak arguments or drop unsupportable ones
- Create an audit trail of your reasoning

**During review:**
- Give reviewers something concrete to evaluate
- Preempt "how do I know?" objections
- Demonstrate methodological rigor without exposing protected data

**After publication:**
- Your paper remains connected to its evidentiary basis
- Future researchers can verify (with appropriate access)
- Your claims are traceable, not just asserted

---

## Who This Is For

- **Qualitative researchers** who want their work taken seriously by skeptics
- **Mixed-methods researchers** who need to integrate qual evidence with quant findings
- **Anyone under IRB** who can't share raw data but wants verifiable claims
- **Reviewers and editors** who want to evaluate evidence without accessing protected transcripts

You don't need to be technical. You don't need to use AI. You need a text editor and a willingness to be explicit about what supports your claims.

---

## How It Works (The Short Version)

1. **You document your claims** — Each substantive claim gets an ID and a text description
2. **You document your evidence** — Quotes, observations, statistics—summarized, not raw
3. **You link them** — Claim X is supported by Evidence Y, challenged by Evidence Z
4. **You run the tool** — It checks your work and generates a verification package
5. **You share the package** — Reviewers see the structure; you keep the raw data

That's it. The tool handles the bookkeeping. You do the thinking.

---

## Getting Started

**New to command-line tools?** Start with our [Getting Started Guide](docs/GETTING_STARTED.md)—it assumes nothing and walks you through every step.

**Comfortable with CLI?** Here's the quick version:

```bash
git clone https://github.com/mattbeane/living-paper.git
cd living-paper
python3 lp.py init
python3 lp.py ingest --claims your_claims.jsonl --evidence your_evidence.jsonl --links your_links.csv
python3 lp.py lint
python3 lp.py prereview --out ./prereview_report.md
python3 lp.py export --out ./verification_package

# NEW in v0.5: Generate reviewer packages
python3 lp.py export-package --paper your-paper-id --out ./reviewer_folder
```

### What's New in v0.5

- **Static HTML Reviewer**: Generate self-contained HTML files reviewers can open in any browser—no server needed
- **Reviewer Packages**: Create complete folders with HTML, README, and double-click launchers (Mac/Windows)
- **Prevalence Metadata**: Track informant coverage, contradicting evidence counts, and saturation notes
- **Contradiction Badges**: Visual highlighting of contradicting evidence in the reviewer interface
- **Entity Redaction**: Built-in tools to anonymize vendor names, sites, and other PII before sharing

### Author Workflow: Preparing Data for Verification

Before generating a reviewer package, authors often need to redact identifying information. Living Paper includes built-in redaction tools:

```bash
# 1. Create your entities file (see entities_example.yaml)
cp entities_example.yaml entities.yaml
# Edit entities.yaml with your specific replacements

# 2. Preview what would be redacted
python3 lp.py redact check --input claims.jsonl --entities entities.yaml

# 3. Apply redaction to files
python3 lp.py redact apply --input claims.jsonl --output claims_redacted.jsonl --entities entities.yaml
python3 lp.py redact apply --input evidence.jsonl --output evidence_redacted.jsonl --entities entities.yaml

# 4. Or redact automatically during ingest
python3 lp.py ingest --claims claims.jsonl --evidence evidence.jsonl --links links.csv --entities entities.yaml
```

The `entities.yaml` file maps identifying names to anonymized labels:

```yaml
vendors:
  Kindred: "Vendor A"
  Vicarious: "Vendor B"
sites:
  Bloomington: "Site Alpha"
projects:
  ACHIEVE: "Project-A"
```

---

## Documentation

| Document | What It Covers |
|----------|----------------|
| [Getting Started](docs/GETTING_STARTED.md) | Step-by-step setup for first-time users |
| [For Authors](docs/FOR_AUTHORS.md) | Complete author workflow: prep, redact, verify, export |
| [Core Concepts](docs/CONCEPTS.md) | The intellectual framework—why this works |
| [Pre-Review Methodology](docs/PREREVIEW.md) | How to use challenges to strengthen your paper |
| [For Reviewers](docs/FOR_REVIEWERS.md) | How to evaluate a living paper verification package |
| [Full Specification](docs/LIVING_PAPER_SPEC.md) | Technical details and future roadmap |

---

## The Hard Question

> "Isn't this just extra work?"

Yes. But it's work you should be doing anyway—making your evidence-claim links explicit. Most researchers do this in their heads or in messy notes. Living Paper gives it structure.

The payoff: fewer R&Rs, stronger papers, and a response to the persistent critique that qualitative findings are unfalsifiable.

---

## No AI Required

Living Paper works entirely with manual input. You create the claim files, evidence files, and links. The tool validates and packages them.

If you *do* use AI-assisted analysis (like [paper-mining-agents](https://github.com/mattbeane/paper-mining-agents)), Living Paper integrates naturally—those tools can generate the input files. But AI is optional.

---

## Requirements

- Python 3.10 or later
- A text editor
- Your claims, evidence, and links in simple file formats (JSON lines, CSV)

No external dependencies. No cloud services. Everything runs on your computer.

---

## Author

Matt Beane
UC Santa Barbara
mattbeane@ucsb.edu

---

## License

MIT. Use it, modify it, share it.
