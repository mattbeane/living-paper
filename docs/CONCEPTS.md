# Core Concepts

This document explains the intellectual framework behind Living Paper. If you want to understand *why* it works the way it does—not just *how* to use it—read on.

---

## The Verification Problem in Qualitative Research

Qualitative research faces a credibility problem that quantitative work largely avoids.

When a quantitative paper reports a regression coefficient, skeptical readers can (in principle) re-run the analysis. The data and code are increasingly available. Even if they aren't, the *path* from data to claim is explicit: these variables, this model, this coefficient.

Qualitative work has no such path. The journey from transcripts to claims happens inside the researcher's head. Reviewers see the output (the paper) but not the process (the analysis). They must trust that the quotes really support the claims, that disconfirming evidence was considered, that the researcher's interpretation is defensible.

This trust-based system has costs:
- Reviewers substitute skepticism for verification
- Authors add more quotes to prove they have data, cluttering the paper
- The critique that qualitative findings are "unfalsifiable" persists
- Replication means starting over, not checking the original

Living Paper addresses this by making claim-evidence links **explicit, structured, and shareable**—while respecting data protection constraints.

---

## Claims as First-Class Objects

In a traditional paper, claims are buried in prose. A sentence in the findings section might contain a claim, a transition, and a framing move, all in one. This makes claims hard to track and verify.

Living Paper treats claims as discrete objects:

```json
{
  "claim_id": "CLM-001",
  "claim_type": "mechanism",
  "text": "Managers used uncertainty about automation timelines to justify process experimentation.",
  "confidence": 0.75
}
```

Each claim has:
- A unique identifier (so you can refer to it unambiguously)
- A type (empirical, mechanism, boundary condition, etc.)
- The claim itself, in plain language
- An optional confidence level

This forces precision. You can't hide a weak claim in a dense paragraph. Every substantive claim stands alone and must be linked to evidence.

---

## Evidence Links Are Typed

Evidence doesn't just "support" claims. The relationship is more nuanced:

| Relation | Meaning |
|----------|---------|
| **supports** | Evidence directly supports the claim |
| **challenges** | Evidence contradicts or complicates the claim |
| **qualifies** | Evidence adds boundary conditions or nuance |
| **illustrates** | Evidence provides a vivid example without being central |
| **necessitates** | Evidence makes the claim necessary (rare) |

Why track challenges? Because honest scholarship requires it. A claim with only supporting evidence looks cherry-picked. A claim with supporting evidence *and* acknowledged challenges looks robust—especially if you've explained how you adjudicate between them.

---

## Three-Tier Access Control

IRB constraints mean you often can't share raw data. Living Paper accommodates this with three tiers:

| Tier | What It Contains | Who Sees It |
|------|------------------|-------------|
| **PUBLIC** | Claim text, evidence summaries, link metadata | Anyone |
| **CONTROLLED** | Anonymized quotes with binned demographics | Approved reviewers |
| **WITNESS_ONLY** | Raw transcripts, identifiable data | Author only |

The PUBLIC tier is your verification package. Reviewers see enough to evaluate your argument structure without accessing protected data.

The CONTROLLED tier allows deeper verification for designated reviewers (e.g., journal-appointed auditors) who agree to data protection terms.

The WITNESS_ONLY tier is your private research archive—pointers to raw data that only you can access.

This layered approach means you can be transparent about your evidence *structure* while protecting participant confidentiality.

---

## The Quant/Qual Hierarchy

When quantitative and qualitative evidence seem to conflict, who wins?

**Living Paper's default: Quantitative findings are almost always ground truth.**

This isn't bias against qualitative work—it's recognition that quant and qual answer different questions:

- **Quantitative data** tells you *what happened* — behaviors, frequencies, outcomes
- **Qualitative data** helps explain *why* it happened — mechanisms, meanings, processes

When a manager says "there was a mass exodus" but your retention data shows 94% stayed, the manager usually isn't *challenging* the retention finding. The manager is demonstrating that their mental model is wrong.

This is valuable evidence! It supports claims like "lay theories about automation effects don't match reality." But it doesn't refute the numbers.

### The Pause: What Might We Be Missing?

That said, when quant and qual contradict, the intellectually honest move is to pause and ask: *what might we be missing?*

Qualitative evidence can sometimes reveal:

1. **Missing variables** — Informants notice something that would explain hidden variation in the quant data. Maybe there *was* an exodus, but in a department or time period your data doesn't cover. Maybe the 94% who stayed includes people who were already planning to leave but delayed.

2. **Falsified or censored records** — In rare cases, qual can reveal that the numbers themselves are wrong. Workers might report that exits were recorded as "transfers" or that headcounts were manipulated.

These are genuinely rare. Most of the time, when qual contradicts quant, the qual perception is wrong. But the pause matters.

### Adjudication Rules

1. **Empirical quant claims** are almost always ground truth
   - Can be challenged by other quant evidence
   - Can *occasionally* be challenged if qual reveals missing data or record problems
   - When qual contradicts quant, first ask: what might the quant be missing?

2. **Qualitative perceptions contradicting quant** should usually be reclassified
   - "Illustrates mistaken beliefs" rather than "challenges"
   - This is itself a finding: informants have wrong mental models

3. **Mechanism claims** can be challenged by qualitative evidence
   - BUT: quantitative behavioral patterns can rule out mechanisms
   - If mechanism X predicts behavior A, but quant shows behavior B, mechanism X is disconfirmed

**Example:** An informant claims workers stayed because they "just didn't care" (apathy). But if retention *increases* as automation approaches and *diverges* by automation type after implementation, apathy can't explain the pattern. Apathy predicts uniform, not divergent, responses. The mechanism claim is eliminated by the quant pattern, not by finding a contradictory quote.

**Counter-example:** A manager says "lots of people left engineering" but your company-wide retention data shows stability. Before dismissing this as a mistaken perception, ask: Does your data include engineering specifically? Could departures be coded as transfers? Is the manager seeing a real pattern in their local context that's masked in aggregate data? Usually the answer is no—but sometimes qual points you toward data you didn't know you were missing.

---

## Pre-Review: Adversarial Collaboration with Yourself

Traditional peer review surfaces problems after you've submitted. You then revise, resubmit, and wait months for another evaluation.

Pre-review surfaces problems *before* submission. Living Paper's `prereview` command identifies:

- **Contested claims** — Evidence cuts both ways; you haven't resolved the tension
- **Weak claims** — Insufficient supporting evidence
- **Challenged claims** — More challenges than supports

For each flagged claim, you receive adjudication prompts appropriate to the claim type:

- For **empirical claims**: Is there quant evidence that contradicts this? If yes, revise or drop.
- For **mechanism claims**: Does the quant behavioral pattern rule out this mechanism? What alternative mechanisms should be considered?

### Why This Isn't P-Hacking

P-hacking is running analyses until you find significance, then pretending that was your hypothesis all along.

Pre-review is different:

| P-Hacking | Pre-Review |
|-----------|------------|
| Change data to fit story | Quantitative data is fixed |
| Hide disconfirming evidence | Surface and engage with challenges |
| Post-hoc rationalization, undocumented | Full audit trail with reasoning |
| Goal: find *a* significant result | Goal: make *your* claims defensible |

The quant data is what it is. You can't "pre-review" your way to different regression coefficients. What you can do is:
- Recognize when a mechanism claim doesn't fit the behavioral pattern
- Reclassify qual evidence that contradicts quant as "illustrates mistaken perception"
- Drop claims you can't defend
- Strengthen claims you can defend with additional evidence

This is good scholarship. The audit trail proves it.

---

## From Static Papers to Living Documents

A traditional paper is frozen at publication. The connection between claims and evidence is severed. If new data emerges, you write a new paper.

A living paper maintains its evidentiary links. This enables:

**Update tracking:** When you add evidence, the system can flag claims that might need revision.

**Verification over time:** Future researchers can verify your claims against your evidence (with appropriate access).

**Explicit revision:** If you change a claim, the history is preserved. Readers see what changed and why.

**Replication support:** Another researcher at the same site (with IRB approval) can verify claims against their own observations, using your claim structure as a template.

---

## The Intellectual Debt

This approach draws on several traditions:

**Analytic philosophy:** Claims should be discrete, evaluable propositions—not rhetorical gestures.

**Reproducibility movement:** The path from data to claim should be documented and verifiable.

**Mixed-methods research:** Quant and qual answer different questions; integration requires explicit rules.

**Adversarial collaboration:** The strongest arguments are those that have survived serious challenges.

Living Paper operationalizes these principles for qualitative researchers working under data protection constraints.

---

## Limitations

**This doesn't solve the fundamental qual problem.** Interpretation is still subjective. Two researchers might look at the same transcript and generate different claims. Living Paper makes your interpretation *explicit*—it doesn't make it *objective*.

**It requires upfront work.** Creating claim, evidence, and link files takes time. For some researchers, this feels like bureaucracy. For others, it's exactly the rigor they want.

**The tool is only as good as your honesty.** If you don't include challenging evidence, the system can't surface it. Living Paper assumes you're trying to do good scholarship, not game the metrics.

**Reviewers need to learn a new format.** The verification package is structured differently than a traditional paper. Some reviewers will find this helpful; others will find it confusing. The [For Reviewers](FOR_REVIEWERS.md) guide helps.

---

## Further Reading

- [Pre-Review Methodology](PREREVIEW.md) — Detailed guidance on engaging with contested claims
- [Full Specification](LIVING_PAPER_SPEC.md) — Technical architecture and future roadmap
- [For Reviewers](FOR_REVIEWERS.md) — How to evaluate a living paper verification package
