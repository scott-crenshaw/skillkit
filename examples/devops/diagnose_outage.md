---
name: diagnose_outage
description: "Lead the incident response workflow for production outages by systematically diagnosing root cause, coordinating mitigation, and restoring service availability."
output_format: structured_report
domain: devops
status: active
domain_areas:
  - Incident Response
task_types:
  - Analyze
  - Debug
version: "2.1"
author: sre_team
tags:
  - incident
  - outage
  - production
  - on-call
---

# Diagnose Outage

## When to Use
Use this skill when a production service is degraded or completely down and you need to figure out what happened and restore service. Activate when monitoring alerts fire for elevated error rates, increased latency, or service unavailability. This skill is appropriate when someone asks "what happened to production?" or "why is the site down?" or "we're getting reports of errors from customers." Also use this when on-call receives a PagerDuty alert for a P1 or P2 incident. This is the primary incident response skill that coordinates the investigation from initial alert through root cause identification and service restoration.

## Steps
1. **Acknowledge the incident**: Confirm the alert, set the incident status to "investigating" in the incident management system, and open an incident channel.
2. **Assess blast radius**: Determine which services, regions, and customers are affected by checking the service dependency map and health dashboards.
3. **Check recent changes**: Review the deployment log for any releases in the last 4 hours. Correlate deployment timestamps with the onset of symptoms.
4. **Examine monitoring data**: Pull up Grafana dashboards for the affected services. Look for anomalies in CPU, memory, disk I/O, network throughput, and request latency.
5. **Analyze application logs**: Search centralized logging (ELK/Splunk) for error spikes, exception traces, and unusual patterns in the time window around incident start. Filter by the affected service name and error severity.
6. **Check infrastructure layer**: Verify that underlying infrastructure (databases, message queues, load balancers, DNS) is healthy. Run connectivity tests between service tiers.
7. **Identify root cause**: Correlate the evidence from logs, metrics, and recent changes to pinpoint the failure. Common patterns include bad deployments, database connection pool exhaustion, certificate expiration, and upstream dependency failures.
8. **Implement mitigation**: Take immediate action to restore service — rollback deployment, restart services, scale up capacity, or failover to backup region.
9. **Verify recovery**: Confirm that error rates have returned to baseline, latency is normal, and monitoring alerts have cleared.
10. **Document findings**: Record the timeline, root cause, mitigation steps, and any follow-up items in the incident record.

## Output Format
A structured incident report with sections: Incident Summary, Timeline (with timestamps), Blast Radius, Root Cause Analysis, Mitigation Actions Taken, Current Status, and Follow-Up Items. Include links to relevant dashboards, log queries, and deployment records.

## Common Pitfalls
- Jumping to conclusions about root cause before gathering sufficient evidence from multiple data sources.
- Not checking the deployment log early enough — bad deploys cause the majority of outages.
- Focusing on symptoms rather than underlying cause, which leads to temporary fixes that fail again.
- Forgetting to communicate status updates to stakeholders while deep in technical investigation.
