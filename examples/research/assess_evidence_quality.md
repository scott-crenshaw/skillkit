---
name: assess_evidence_quality
description: "Evaluate the strength and reliability of evidence presented in a research paper or collection of studies, using established evidence quality frameworks."
output_format: structured_report
domain: research
status: draft
domain_areas:
  - Research
task_types:
  - Classify
  - Analyze
version: "0.8"
author: research_team
tags:
  - academic
  - evidence
  - quality
  - evaluation
---

# Assess Evidence Quality

## When to Use
Use this skill when you need to determine how much confidence to place in a research finding or set of findings. Activate when someone asks "how strong is this evidence?" or "can we trust this study?" or "what level of evidence does this represent?" This skill applies structured evidence quality frameworks to rate the strength of research evidence. It is useful for informing decision-making — understanding whether a finding is robust enough to act on, or whether more evidence is needed before committing resources.

## Steps
1. **Identify the evidence type**: Classify the source according to the evidence hierarchy — systematic review or meta-analysis, randomized controlled trial, cohort study, case-control study, cross-sectional study, case report, or expert opinion.
2. **Apply the GRADE framework**: Use the Grading of Recommendations, Assessment, Development and Evaluations (GRADE) approach to assess four dimensions:
   - **Risk of bias**: Are there methodological flaws that could distort the findings? Check for selection bias, measurement bias, attrition, and reporting bias.
   - **Inconsistency**: If multiple studies exist, do they reach similar conclusions? Unexplained heterogeneity reduces confidence.
   - **Indirectness**: Does the evidence directly address the question at hand, or is it indirect (different population, different intervention, surrogate outcomes)?
   - **Imprecision**: Are the confidence intervals narrow enough to support the conclusion? Small sample sizes and wide intervals indicate imprecision.
3. **Check for publication bias**: Consider whether the evidence base may be skewed by selective publication of positive results. Look for funnel plot asymmetry in meta-analyses or an absence of null-result studies.
4. **Evaluate the funding and conflict of interest**: Note the funding sources and any declared conflicts of interest. Assess whether these could influence the study design, analysis, or reporting.
5. **Consider the replication status**: Has the finding been replicated by independent teams? Single unreplicated findings, regardless of methodology quality, should be treated as preliminary.
6. **Assign an overall quality rating**: Based on the accumulated assessment, assign the evidence one of four quality levels: High, Moderate, Low, or Very Low.
7. **Write the quality justification**: Document the reasoning behind the assigned rating, noting which factors increased or decreased confidence.

## Output Format
A structured evidence quality report with sections: Evidence Classification, GRADE Assessment (with ratings for each dimension), Publication Bias Assessment, Conflict of Interest Review, Replication Status, Overall Quality Rating, and Justification Narrative. Include a one-sentence bottom line statement summarizing the confidence level.

## Common Pitfalls
- Equating study type with evidence quality — a well-conducted observational study can provide stronger evidence than a poorly designed RCT.
- Ignoring publication bias, which is particularly problematic in fields with strong commercial interests.
- Not considering the totality of evidence — rating quality based on a single study when a body of literature exists.
- Applying the framework mechanically without using judgment about the specific context and question being addressed.
