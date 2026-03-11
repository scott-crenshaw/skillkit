---
name: extract_methodology
description: "Extract and analyze the research methodology from an academic paper, documenting the study design, data collection procedures, analytical techniques, and methodological limitations."
output_format: structured_report
domain: research
status: active
domain_areas:
  - Research
task_types:
  - Analyze
version: "1.0"
author: research_team
tags:
  - academic
  - methodology
  - papers
  - analysis
---

# Extract Methodology

## When to Use
Use this skill when you need a detailed breakdown of how a research study was conducted. Activate when someone asks "what methodology did this paper use?" or "how was this study designed?" or "walk me through the research methods." This skill reads the full text of an academic paper — particularly the methods, data, and analysis sections — and produces a detailed methodological profile. It is useful when evaluating whether a study's methods are appropriate for its research question, when replicating a study's approach, or when assessing the credibility of findings based on methodological rigor. Also use this when comparing methodological approaches across multiple papers in a literature review.

## Steps
1. **Identify the research design**: Classify the study type — randomized controlled trial, quasi-experimental, observational cohort, cross-sectional survey, case study, meta-analysis, qualitative, or mixed methods.
2. **Document the sample**: Record the sample size, population characteristics, sampling method (random, convenience, stratified, snowball), inclusion and exclusion criteria, and any demographic breakdowns reported.
3. **Map the data collection**: Describe how data was gathered — surveys, interviews, administrative records, sensor data, web scraping, or existing datasets. Note the time period of data collection and any instruments or tools used.
4. **Extract the analytical approach**: Detail the statistical or qualitative methods used for analysis. For quantitative studies, note the specific tests (regression, ANOVA, chi-square, etc.), significance thresholds, and any corrections applied. For qualitative studies, note the coding approach and theoretical framework.
5. **Identify control variables**: List what variables the study controlled for and how. Note any potential confounds that were not addressed.
6. **Assess validity and reliability**: Evaluate internal validity (did the design actually test what it claims?), external validity (how generalizable are the results?), and reliability (would the study produce similar results if repeated?).
7. **Document limitations**: Catalog methodological limitations both acknowledged by the authors and any additional ones apparent from the design.
8. **Rate methodological rigor**: Provide an overall assessment of the methodology's appropriateness for the research question and the quality of execution.

## Output Format
A structured methodology profile with sections: Research Design Classification, Sample Description, Data Collection Methods, Analytical Approach, Controls and Variables, Validity Assessment, Limitations, and Overall Rigor Rating (High/Moderate/Low). Include specific details such as sample sizes, statistical tests, and significance thresholds.

## Common Pitfalls
- Accepting the authors' description of their methodology at face value without checking whether the execution matches the claimed design.
- Not distinguishing between the intended methodology and what was actually possible given data limitations.
- Overlooking selection bias in sample recruitment, which can undermine the entire study's conclusions.
- Failing to note when standard methodological practices (like pre-registration or power analysis) were absent.
