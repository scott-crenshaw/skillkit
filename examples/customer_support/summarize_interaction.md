---
name: summarize_interaction
description: "Generate a concise summary of a completed customer support interaction for internal records, quality review, and handoff continuity."
output_format: structured_report
domain: customer_support
status: draft
domain_areas:
  - Customer Service
task_types:
  - Summarize
version: "0.9"
author: cs_team
tags:
  - summary
  - documentation
  - quality
---

# Summarize Interaction

## When to Use
Use this skill at the end of a customer support interaction to create a standardized summary for the ticket record. Activate after the customer's issue has been resolved or the conversation has ended, before the ticket is closed. This summary serves three purposes: it enables other agents to quickly understand what happened if the customer contacts support again, it feeds into quality assurance review workflows, and it provides data for trend analysis across support interactions.

## Steps
1. Review the complete interaction transcript including all agent and customer messages.
2. Identify the key elements of the interaction:
   - **Customer intent**: What the customer originally contacted support about.
   - **Issue details**: Specific product, order, or account involved.
   - **Resolution**: What action was taken to address the issue.
   - **Outcome**: Whether the customer's issue was fully resolved, partially resolved, or unresolved.
   - **Sentiment**: Customer's apparent satisfaction at the end of the interaction.
3. Extract any commitments made to the customer (e.g., "refund will appear in 3-5 days").
4. Note any follow-up actions required by other teams.
5. Identify if any policy exceptions were made and by whom.
6. Compile the summary in the standard template format.
7. Flag any quality concerns such as long hold times, multiple transfers, or customer frustration indicators.
8. Attach relevant metadata: interaction duration, number of messages, skills used during the session.

## Output Format
A structured report with clearly labeled sections: Customer Intent, Issue Details, Actions Taken, Resolution Status, Customer Sentiment, Follow-Up Required, and Quality Flags. Each section should be two to three sentences maximum for quick scanning by reviewers.

## Common Pitfalls
- Writing summaries that are too verbose, defeating the purpose of a quick-scan document.
- Omitting commitments made to the customer, which leads to broken promises when they call back.
- Not distinguishing between "resolved" and "customer accepted workaround" as different outcomes.
- Missing quality flags that would help identify systemic support process issues.
