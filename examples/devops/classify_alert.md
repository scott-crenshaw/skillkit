---
name: classify_alert
description: "Evaluate incoming monitoring alerts to determine severity, assign priority, and route to the correct response team based on alert context and historical patterns."
output_format: classification
domain: devops
status: active
domain_areas:
  - Monitoring
task_types:
  - Classify
version: "1.2"
author: sre_team
tags:
  - alerts
  - monitoring
  - triage
  - on-call
---

# Classify Alert

## When to Use
Use this skill when a new monitoring alert arrives and needs to be triaged before action is taken. This is the entry point for alert processing — every alert from PagerDuty, Datadog, CloudWatch, or other monitoring tools passes through this classification step. Activate when the on-call engineer receives a notification and needs to quickly determine if it requires immediate action, can wait until business hours, or is a false positive that should be suppressed.

## Steps
1. **Parse alert metadata**: Extract the source system, alert name, severity tag, affected resource, metric value, threshold breached, and timestamp from the incoming alert payload.
2. **Check for known patterns**: Compare the alert against the known-issues database and recent incident records. If this exact alert has been seen before and has a documented response, flag it as a known pattern.
3. **Assess service impact**: Determine which customer-facing services depend on the affected resource using the service dependency map. An alert on a non-critical batch processing system has different urgency than one on the payment gateway.
4. **Evaluate severity**:
   - **P1 Critical**: Customer-facing service is down or data loss is occurring. Immediate response required.
   - **P2 High**: Service is degraded but functional. Response within 30 minutes.
   - **P3 Medium**: Non-customer-facing system affected or metric is trending toward threshold. Response within 4 hours.
   - **P4 Low**: Informational alert, capacity planning trigger, or non-urgent maintenance item. Next business day.
5. **Check for alert correlation**: Look for related alerts that fired around the same time. Multiple alerts from different services often indicate a shared root cause at the infrastructure layer.
6. **Route the alert**: Based on classification, route to the appropriate team — SRE for infrastructure, application team for service-specific issues, DBA for database alerts, or security for access anomalies.
7. **Suppress if false positive**: If the alert matches known false-positive patterns (e.g., brief metric spikes during scheduled maintenance windows), auto-acknowledge and log for review.

## Output Format
A classification result containing: Alert ID, Assigned Priority (P1-P4), Impact Assessment (services and customers affected), Correlation Group (related alerts if any), Routing Destination (team and channel), and Recommended Action (immediate response steps or "monitor and wait").

## Common Pitfalls
- Treating all alerts as equal urgency, which leads to alert fatigue and slow response to real incidents.
- Not checking for correlated alerts, which results in multiple teams investigating the same root cause independently.
- Auto-suppressing alerts too aggressively, which causes real issues to be missed during maintenance windows.
- Failing to update the known-issues database after resolving new alert patterns.
