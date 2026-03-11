---
name: analyze_logs
description: "Search, filter, and analyze application and infrastructure logs to identify error patterns, performance anomalies, and operational issues in production systems."
output_format: structured_report
domain: devops
status: active
domain_areas:
  - Monitoring
task_types:
  - Analyze
version: "1.5"
author: sre_team
tags:
  - logs
  - monitoring
  - debugging
  - production
---

# Analyze Logs

## When to Use
Use this skill when you need to investigate what happened in production by examining log data. Activate when someone asks "can you check the logs?" or "what do the error logs show?" or "why are we seeing these errors?" This skill is focused specifically on log search and pattern extraction — finding the relevant entries in potentially massive log volumes and making sense of them. Use this for targeted log analysis tasks such as tracing a specific request, identifying recurring error patterns, or measuring error frequency over time. Also appropriate after an outage has been resolved to do deeper forensic analysis of the log trail.

## Steps
1. **Define the search scope**: Identify which services, time range, and log levels to search. Narrow the scope as much as possible to avoid noise.
2. **Build the query**: Construct a search query using the logging platform's query language (KQL for Azure, Lucene for ELK, SPL for Splunk). Include service name, time bounds, and severity filters.
3. **Execute initial broad search**: Run the query to get a high-level view of log volume, error distribution, and top error messages in the time window.
4. **Identify error clusters**: Group similar log entries by error message template, removing variable components like IDs and timestamps. Rank clusters by frequency.
5. **Trace specific requests**: For errors affecting individual users or requests, use correlation IDs or trace IDs to follow a single request across service boundaries.
6. **Analyze temporal patterns**: Plot error frequency over time to identify whether errors are constant, increasing, periodic, or correlated with specific events like deployments or traffic spikes.
7. **Extract stack traces**: For application errors, pull full stack traces and identify the code paths that are failing. Map these to recent code changes if applicable.
8. **Cross-reference with metrics**: Compare log patterns with infrastructure metrics (CPU, memory, connection counts) to identify resource-related causes.
9. **Summarize findings**: Compile the key patterns, error clusters, and notable entries into a structured analysis report.

## Output Format
A structured analysis report containing: Search Parameters (services, time range, query used), Error Summary (top error clusters with counts), Temporal Analysis (pattern description and peak times), Notable Entries (specific log lines that reveal the issue), and Recommendations (suggested next steps based on findings).

## Common Pitfalls
- Searching too broad a time range or too many services at once, which produces overwhelming and noisy results.
- Ignoring warning-level logs that often contain early indicators of problems before errors start appearing.
- Not using correlation IDs to trace requests, leading to incomplete picture of multi-service failures.
- Confusing log volume with severity — a high count of info-level logs is not the same as a critical issue.
