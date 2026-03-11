---
name: generate_postmortem
description: "Generate a blameless postmortem document from incident data, including timeline reconstruction, root cause analysis, and actionable follow-up items."
output_format: structured_report
domain: devops
status: deprecated
domain_areas:
  - Incident Response
task_types:
  - Generate
  - Summarize
version: "1.0"
author: sre_team
tags:
  - postmortem
  - incident
  - documentation
---

# Generate Postmortem

## When to Use
Use this skill after a production incident has been fully resolved and the team is ready to conduct a postmortem review. Activate when the incident manager requests a postmortem document, typically within 48 hours of incident resolution. This skill compiles information from the incident channel, monitoring systems, and deployment records into a structured blameless postmortem following the organization's standard template.

## Steps
1. **Gather incident data**: Collect the incident record, chat transcripts from the incident channel, alert history, and deployment logs covering the incident window.
2. **Reconstruct the timeline**: Build a minute-by-minute timeline from the first alert to full resolution. Include key decision points, mitigation attempts, and communication milestones.
3. **Identify contributing factors**: List all factors that contributed to the incident. Distinguish between the trigger (what started it), the propagation (why it spread), and the detection gap (why it wasn't caught sooner).
4. **Write the root cause analysis**: Describe the technical root cause in clear language. Use the "5 Whys" technique to go beyond the surface-level trigger.
5. **Assess the response**: Evaluate how the incident response went — what worked well, what could be improved. Note any gaps in runbooks, monitoring, or communication.
6. **Generate action items**: Create specific, assignable follow-up items with owners and due dates. Categorize as: prevent recurrence, improve detection, or improve response.
7. **Calculate impact metrics**: Document the duration, affected customers, error budget consumed, revenue impact (if measurable), and SLA implications.
8. **Draft the executive summary**: Write a two-paragraph summary suitable for leadership, covering what happened, the customer impact, and the key corrective actions.
9. **Review for blamelessness**: Ensure the document focuses on systems and processes rather than individual mistakes. Remove any language that assigns personal blame.

## Output Format
A structured postmortem document with sections: Executive Summary, Incident Timeline, Root Cause Analysis, Contributing Factors, Impact Assessment, What Went Well, What Could Be Improved, and Action Items (with owner, priority, and due date). The document should be suitable for both technical and non-technical audiences.

## Common Pitfalls
- Writing the postmortem weeks after the incident when memories have faded and details are lost.
- Focusing on blame rather than systemic improvements, which discourages honest reporting.
- Creating action items that are too vague to be actionable (e.g., "improve monitoring" instead of "add latency alert for payment service at p99 > 500ms").
- Not following up on action items, which makes future postmortems feel pointless.
