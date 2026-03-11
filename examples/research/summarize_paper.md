---
name: summarize_paper
description: "Read an academic research paper and produce a structured summary covering the research question, methodology, key findings, and practical implications."
output_format: structured_report
domain: research
status: active
domain_areas:
  - Research
task_types:
  - Summarize
version: "1.3"
author: research_team
tags:
  - academic
  - papers
  - summary
  - literature
---

# Summarize Paper

## When to Use
Use this skill when you need to quickly understand the content of an academic research paper or journal article. Activate when someone asks "summarize this paper," "what does this study say?", or "give me the key takeaways from this research." This skill is designed for processing academic publications including peer-reviewed journal articles, conference papers, preprints, and working papers. It reads the full text of the paper and extracts the essential information into a scannable format. Also use this when building a literature review and you need to process multiple papers efficiently, or when a stakeholder needs a non-technical briefing on recent research relevant to a project.

## Steps
1. **Read the abstract**: Start with the abstract to get the paper's own summary of its contribution. Note the stated research question, methodology, and main findings.
2. **Identify the research question**: Articulate the specific question or hypothesis the paper addresses. If the paper has multiple research questions, list them in order of prominence.
3. **Extract the methodology**: Note the research design (experimental, observational, meta-analysis, theoretical), sample size, data sources, and analytical methods used. Flag any novel methodological contributions.
4. **Catalog key findings**: List the main results, including statistical significance levels, effect sizes, and confidence intervals where reported. Distinguish between primary and secondary findings.
5. **Assess limitations**: Identify the limitations the authors acknowledge and any additional limitations apparent from the methodology or data.
6. **Capture practical implications**: Note what the findings mean for practitioners, policy, or future research directions as discussed by the authors.
7. **Evaluate the evidence quality**: Rate the overall evidence strength based on study design, sample size, methodology rigor, and potential biases.
8. **Write the structured summary**: Compile all extracted information into the standard output template, keeping each section concise and using accessible language.
9. **Add citation information**: Include the full citation in a standard format for reference management.

## Output Format
A structured summary report with sections: Citation, Research Question, Methodology Overview, Key Findings (bulleted list), Limitations, Practical Implications, and Evidence Quality Rating (Strong/Moderate/Preliminary). Total summary length should be 300-500 words, suitable for rapid review.

## Common Pitfalls
- Summarizing only the abstract without reading the full paper, which misses nuances and limitations disclosed in later sections.
- Conflating correlation with causation when restating findings from observational studies.
- Ignoring the limitations section, which is critical for assessing how much weight to give the findings.
- Using overly technical jargon in the summary that makes it inaccessible to non-specialist readers.
