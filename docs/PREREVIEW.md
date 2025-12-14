# Pre-Review: Adversarial Self-Audit Before Submission

## What This Is

Pre-review is a systematic process of engaging with contested claims and challenging evidence **before** external reviewers do. The living paper system surfaces tensions; pre-review resolves them through principled reasoning.

This is a feature, not a bug.

## Why This Isn't P-Hacking

| P-Hacking | Pre-Review |
|-----------|------------|
| Change data to fit story | Data is ground truth, unchanged |
| Hide disconfirming evidence | Surface and engage with challenges |
| Post-hoc rationalization | Principled adjudication with clear rules |
| Undocumented | Full audit trail in claim revisions |

The key distinction: **quant findings are fixed**. Pre-review refines mechanism claims and interpretations, not empirical results.

## The Quant/Qual Hierarchy

When adjudicating contested claims:

1. **Empirical claims (quant)** = ground truth
   - Only challengeable by other quant evidence
   - Qual perceptions that contradict quant → mistaken beliefs, not challenges

2. **Mechanism claims (theoretical)** = interpretations
   - Can be challenged by qual evidence
   - BUT: quant patterns can rule out mechanisms via behavioral implications
   - If mechanism X predicts behavior A, but quant shows behavior B, mechanism X is disconfirmed

3. **Qual evidence about quant claims**
   - Reclassify as "illustrates mistaken beliefs" not "challenges"
   - Often supports claims about lay theories being wrong

## Pre-Review Workflow

### 1. Surface Contested Claims
```bash
python lp.py lint              # Check all claims have evidence
python lp.py visualize         # See health indicators
```

Look for:
- Red/yellow indicators (challenged/contested)
- MECHANISM claims with challenges
- Low confidence scores

### 2. Engage Each Contested Claim

For each contested claim, ask:

**If QUANT claim challenged by qual:**
- Is the qual evidence about perceptions/beliefs or actual data?
- If perceptions → reclassify as supports lay-theory-is-wrong claims
- If actual competing data → genuine challenge, investigate

**If MECHANISM claim challenged:**
- What does this mechanism predict behaviorally?
- Does the quant pattern match the prediction?
- Can competing mechanisms be ruled out by quant patterns?

### 3. Document Reasoning

Update links with reasoning:
```
# Before
EV-008,CLM-003,challenges,central,75% workforce shows no care

# After
EV-008,CLM-003,qualifies,supporting,Manager perceives apathy - but apathy cant explain retention increase or robot/sorter divergence
```

### 4. Adjust Confidence

Based on adjudication:
- Mechanism survives quant test → increase confidence
- Mechanism ruled out by quant → decrease or retract
- Genuine ambiguity remains → note in claim text

## Example: Adjudicating a Mechanism Claim

**Claim:** Workers engage in "anticipatory sensemaking" - staying to understand a change before deciding whether to leave

**Challenge:** Manager interview says "most workers don't care about the changes" (apathy)

**Adjudication:**
1. If apathy is the true mechanism → predict NO behavior change when change announced
2. If apathy → predict NO differential response to different types of change
3. Quant shows: retention INCREASES when change announced, and response DIFFERS by change type
4. Conclusion: Apathy can't explain the pattern. Workers ARE responding differentially.

The manager's perception is wrong—contradicted by behavioral data. The qual evidence gets reclassified from "challenges" to "illustrates mistaken managerial beliefs."

**Result:**
- Confidence 0.6 → 0.75 (mechanism survives quant test)
- Challenge reclassified as "qualifies" with reasoning documented
- New insight: Manager perceptions may be systematically biased

## What Pre-Review Produces

1. **Stronger claims** - survived adversarial scrutiny
2. **Better reasoning** - explicit logic for mechanism support
3. **Audit trail** - revision history shows engagement with challenges
4. **Preempted reviewer objections** - already addressed obvious challenges
5. **Sometimes: new findings** - engagement surfaces patterns you missed

## Guardrails

To prevent slipping into p-hacking:

1. **Never change quant data** - it's fixed
2. **Document all reclassifications** - transparent reasoning
3. **Preserve original challenge classification** - in revision history
4. **Apply rules consistently** - same logic across all claims
5. **Accept disconfirmation** - if quant rules out your mechanism, retract it
