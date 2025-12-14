# For Reviewers: Evaluating a Living Paper

You've received a verification package from an author using Living Paper. This guide explains what you're looking at and how to evaluate it.

---

## What You've Received

A verification package typically contains:

1. **claims.json** — Every substantive claim in the paper, with unique identifiers
2. **evidence_summaries.json** — Non-identifying summaries of supporting and challenging evidence
3. **links.json** — The connections between claims and evidence, with relationship types
4. **health_report.html** — A visual dashboard showing claim status (open this in a browser)

You may also receive the manuscript itself, formatted traditionally, with claim IDs in the margins or footnotes.

---

## What You Can Verify

### 1. Claim-Evidence Structure

For each claim, you can see:
- What evidence supports it
- What evidence challenges it
- How the author weights each piece of evidence
- The author's stated confidence level

**This is more than you get with a traditional paper.** You're seeing the skeleton of the argument, not just the polished prose.

### 2. Engagement with Contradictions

Look for claims that have both supporting and challenging evidence. Check:
- Does the author acknowledge the tension?
- Is there a plausible resolution?
- Or is the claim overclaimed given the mixed evidence?

A paper with *no* challenging evidence should raise flags. Either the phenomenon is unambiguously clear (rare), or the author didn't look hard enough (common).

### 3. Evidence Distribution

Are all claims well-supported, or do some rest on a single piece of evidence? The health report visualizes this:
- **Green:** Strong support, minimal challenges
- **Yellow:** Moderate support or some tension
- **Red:** Weak support or contested

A paper can have some yellow or red claims—that's honest. What matters is whether the author acknowledges uncertainty where it exists.

---

## What You Cannot Verify

### Raw Data

You likely don't have access to the actual transcripts, field notes, or observations. The evidence summaries are non-identifying descriptions—paraphrases, not quotes.

**This is intentional.** IRB constraints often prohibit sharing identifiable data. The author is showing you that evidence *exists* and *links* to claims, even if you can't read the original.

### Interpretation Quality

Two researchers might code the same transcript differently. Living Paper doesn't validate the author's interpretation—it makes that interpretation explicit so you can evaluate it.

Ask yourself: Given the evidence summaries provided, is the author's interpretation plausible? Defensible? Or does it seem like a stretch?

---

## Red Flags to Watch For

### 1. No Challenging Evidence
If every claim has only supporting evidence, the author may not be engaging honestly with their data. Qualitative fieldwork almost always surfaces contradictions.

### 2. Central Claims with Peripheral Evidence
If a key claim rests only on evidence marked "peripheral" or "illustrative," the claim may be overclaimed.

### 3. Mechanism Claims Contradicted by Patterns
For causal mechanism claims, check whether the proposed mechanism is consistent with behavioral patterns. If a manager claims workers stayed due to apathy, but retention *diverged* by automation type, apathy can't explain the divergence.

### 4. Missing Evidence IDs
If the paper references claims that don't appear in the verification package, ask why. Did something get dropped?

---

## Controlled Access

If the author offers CONTROLLED-tier access, you may be able to see more:
- Anonymized quotes (not just summaries)
- Binned demographic information
- Additional context

This typically requires:
1. Agreement to data protection terms
2. Access through a secure environment (no downloading/exporting)
3. Coordination with the author

If you want controlled access, contact the author directly. Journals may also establish formal processes for auditor access.

---

## What to Ask For

If the verification package is incomplete, you can request:

1. **Evidence for specific claims:** "Please provide more detail on the evidence supporting CLM-003."

2. **Explanation of tensions:** "EVD-012 seems to challenge CLM-005. How do you reconcile this?"

3. **Controlled access:** "I'd like to review the anonymized quotes in a secure environment."

4. **Audit trail:** "What revisions did you make during pre-review, and why?"

The author should be able to provide these. If they can't, the Living Paper infrastructure wasn't used fully—or wasn't used honestly.

---

## Evaluating Claim Health

The health report uses simple indicators:

| Status | Meaning | Your Response |
|--------|---------|---------------|
| **Supported** | Multiple supporting links, minimal challenges | Looks good |
| **Qualified** | Supported, but with acknowledged boundary conditions | Check that qualifications make it to the paper |
| **Contested** | Significant challenging evidence | Ask how the author adjudicates |
| **Weak** | Few supporting links, or low author confidence | Ask for more evidence or reduced claims |
| **Challenged** | More challenges than supports | Should probably be revised or dropped |

A good paper can have contested claims if the author engages with the tension. A bad paper has contested claims that the author ignores.

---

## The Bottom Line

Living Paper gives you visibility into the author's reasoning that you don't get from a traditional submission. Use it.

You're not expected to verify every claim against raw data—that's often impossible. You *are* expected to evaluate whether:
- The claim-evidence structure is coherent
- Contradictions are acknowledged and addressed
- The author's confidence matches the evidence

This is a higher bar than "the quotes seem relevant." It's also a more meaningful evaluation.

---

## Questions?

If you're confused by a verification package, contact the author. If you have questions about Living Paper itself, see [github.com/mattbeane/living-paper](https://github.com/mattbeane/living-paper) or email mattbeane@ucsb.edu.
