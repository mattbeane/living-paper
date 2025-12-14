# Getting Started with Living Paper

This guide walks you through setting up and using Living Paper from scratch. It assumes no prior experience with command-line tools, Git, or programming.

---

## What You'll Need

1. **A computer** running macOS, Windows, or Linux
2. **Python 3.10 or later** (we'll check this together)
3. **A text editor** (any will do—even Notepad or TextEdit)
4. **Your research materials** — claims you want to make, evidence that supports them

That's it. No special software to buy, no accounts to create.

---

## Step 1: Check If You Have Python

Python is a programming language that comes pre-installed on many computers. Living Paper uses it to run.

### On Mac

1. Open the **Terminal** app (search for "Terminal" in Spotlight, or find it in Applications → Utilities)
2. Type this and press Enter:
   ```
   python3 --version
   ```
3. You should see something like `Python 3.11.4`. Any version 3.10 or higher works.

**If you don't have Python or it's too old:** Download it from [python.org/downloads](https://www.python.org/downloads/). Install it like any other app.

### On Windows

1. Open **Command Prompt** (search for "cmd" in the Start menu)
2. Type this and press Enter:
   ```
   python --version
   ```
3. You should see something like `Python 3.11.4`.

**If you don't have Python:** Download it from [python.org/downloads](https://www.python.org/downloads/). During installation, **check the box that says "Add Python to PATH"**—this is important.

---

## Step 2: Download Living Paper

You have two options:

### Option A: Download as a ZIP file (easiest)

1. Go to [github.com/mattbeane/living-paper](https://github.com/mattbeane/living-paper)
2. Click the green **Code** button
3. Click **Download ZIP**
4. Unzip the file somewhere you'll remember (like your Documents folder)

### Option B: Use Git (if you have it)

If you're comfortable with Git:
```
git clone https://github.com/mattbeane/living-paper.git
```

---

## Step 3: Open Terminal in the Living Paper Folder

### On Mac

1. Open Terminal
2. Type `cd ` (with a space after it)
3. Drag the living-paper folder from Finder into the Terminal window
4. Press Enter

You should see your prompt change to show you're in the living-paper folder.

### On Windows

1. Open the living-paper folder in File Explorer
2. Click in the address bar at the top
3. Type `cmd` and press Enter

This opens Command Prompt directly in that folder.

---

## Step 4: Initialize Living Paper

Now we'll set up the databases where Living Paper stores your claims and evidence.

Type this and press Enter:
```
python3 lp.py init
```

(On Windows, you might need to use `python` instead of `python3`)

You should see:
```
Initialized living paper databases in ./
```

This creates two database files:
- `lp_public.sqlite` — Safe to share; contains claim metadata
- `lp_private.sqlite` — Keep private; contains pointers to your raw data

---

## Step 5: Create Your Input Files

Living Paper needs three files from you:

### 1. Claims file (`claims.jsonl`)

Each line is one claim. Here's an example:

```json
{"claim_id": "CLM-001", "paper_id": "my-paper", "claim_type": "mechanism", "text": "Experienced workers taught newcomers through informal mentoring despite official training programs."}
{"claim_id": "CLM-002", "paper_id": "my-paper", "claim_type": "empirical", "text": "Informal mentoring occurred in 73% of observed training sessions."}
```

**Fields explained:**
- `claim_id`: A unique identifier (you make this up—just be consistent)
- `paper_id`: An identifier for your paper (useful if you have multiple papers)
- `claim_type`: What kind of claim is this?
  - `empirical` — Based on observed/measured data
  - `mechanism` — Explains *why* something happens
  - `descriptive` — Describes what you observed
  - `boundary_condition` — When/where the finding applies
- `text`: The actual claim, in plain language

### 2. Evidence file (`evidence.jsonl`)

Each line is one piece of evidence. Here's an example:

```json
{"evidence_id": "EVD-001", "paper_id": "my-paper", "evidence_type": "quote", "summary": "Senior technician describes showing new hires 'the real way' after official training.", "sensitivity_tier": "PUBLIC", "meta": {"informant_role": "technician", "interview_id": "INT-012"}}
{"evidence_id": "EVD-002", "paper_id": "my-paper", "evidence_type": "observation", "summary": "Observed senior worker pulling aside trainee during break to demonstrate shortcut.", "sensitivity_tier": "PUBLIC", "meta": {"observation_id": "OBS-034"}}
```

**Fields explained:**
- `evidence_id`: Unique identifier
- `evidence_type`: What kind of evidence?
  - `quote` — Something someone said
  - `observation` — Something you witnessed
  - `fieldnote` — Your written notes
  - `quant_output` — Statistical result
- `summary`: A non-identifying description (this is what reviewers see)
- `sensitivity_tier`: How protected is this evidence?
  - `PUBLIC` — Safe to share with anyone
  - `CONTROLLED` — Share only with approved reviewers
  - `WITNESS_ONLY` — Author access only
- `meta`: Additional metadata (role, site, interview ID—whatever your IRB allows)

### 3. Links file (`links.csv`)

This connects claims to evidence. It's a simple spreadsheet format:

```csv
claim_id,evidence_id,relation,weight,note
CLM-001,EVD-001,supports,central,Core evidence for informal mentoring claim
CLM-001,EVD-002,supports,supporting,Additional observational support
CLM-002,EVD-003,supports,central,Direct count from observations
CLM-001,EVD-004,challenges,supporting,One manager denied informal training occurred
```

**Fields explained:**
- `claim_id`: Which claim
- `evidence_id`: Which evidence
- `relation`: How does the evidence relate to the claim?
  - `supports` — Evidence supports the claim
  - `challenges` — Evidence contradicts or complicates the claim
  - `qualifies` — Evidence adds nuance or boundary conditions
  - `illustrates` — Evidence provides a vivid example
- `weight`: How important is this evidence?
  - `central` — Core evidence; claim depends on it
  - `supporting` — Additional evidence; strengthens the claim
  - `peripheral` — Minor evidence; nice to have
- `note`: Your explanation (optional but helpful)

---

## Step 6: Ingest Your Files

Once you've created your three files, tell Living Paper to load them:

```
python3 lp.py ingest --claims claims.jsonl --evidence evidence.jsonl --links links.csv
```

You should see something like:
```
Ingested 12 claims, 34 evidence items, 56 links
```

---

## Step 7: Check for Problems

Run the linter to catch issues:

```
python3 lp.py lint
```

If everything is okay:
```
All checks passed.
```

If there are problems, you'll see specific error messages like:
```
ERROR: Claim CLM-005 has no supporting evidence
WARNING: Evidence EVD-012 is not linked to any claim
```

Fix these issues in your input files and run `ingest` again.

---

## Step 8: Generate a Pre-Review Report

This is where Living Paper gets powerful. It surfaces claims that need attention:

```
python3 lp.py prereview
```

This creates a report showing:
- **Contested claims** — Evidence cuts both ways
- **Weak claims** — Not enough supporting evidence
- **Challenged claims** — More challenges than supports

For each flagged claim, you'll see prompts to help you think through whether the claim should be revised, supported with more evidence, or dropped.

---

## Step 9: Export Your Verification Package

When you're ready to share with reviewers:

```
python3 lp.py export --out ./verification_package
```

This creates a folder containing:
- `claims.json` — All your claims with their evidence links
- `evidence_summaries.json` — Non-identifying summaries of your evidence
- `health_report.html` — A visual dashboard of claim health

You can send this folder to reviewers. They see the structure of your argument; they don't see your raw transcripts.

---

## Common Questions

### "I made a mistake in my files. How do I fix it?"

Edit your `.jsonl` or `.csv` files, then run the `ingest` command again. Living Paper will update its databases.

### "Can I use Excel instead of CSV?"

Yes! Create your links in Excel, then save as CSV (File → Save As → CSV).

### "What if I have hundreds of claims?"

That's fine. Living Paper handles any size. Just be consistent with your IDs.

### "Do I need to be online?"

No. Everything runs locally on your computer. Your data never leaves your machine.

### "I'm getting a 'command not found' error"

Make sure you're in the living-paper folder (Step 3). If `python3` doesn't work, try `python`.

### "How do I update Living Paper later?"

If you used Git: `git pull`
If you downloaded the ZIP: Download a fresh copy and replace your files (keep your data files separate).

---

## Next Steps

Once you're comfortable with the basics:

1. Read [Core Concepts](CONCEPTS.md) to understand the intellectual framework
2. Review [Pre-Review Methodology](PREREVIEW.md) for guidance on engaging with contested claims
3. Share [For Reviewers](FOR_REVIEWERS.md) with anyone evaluating your verification package

---

## Getting Help

- **Email:** mattbeane@ucsb.edu
- **GitHub Issues:** [github.com/mattbeane/living-paper/issues](https://github.com/mattbeane/living-paper/issues)

If you're stuck, email me. I want this tool to be usable by real qualitative researchers, and your confusion points help me improve the documentation.
