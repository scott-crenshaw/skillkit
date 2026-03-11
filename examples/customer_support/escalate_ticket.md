---
name: escalate_ticket
description: "Escalate complex customer issues that require manager approval, including refund exceptions, policy overrides, and high-value dispute resolution."
output_format: text
domain: customer_support
status: active
domain_areas:
  - Customer Service
task_types:
  - Classify
  - Recommend
version: "1.0"
author: cs_team
tags:
  - escalation
  - refund
  - dispute
---

# Escalate Ticket

## When to Use
Use this skill when a customer's request exceeds standard support authority and requires manager intervention. This includes refund requests that fall outside the normal return window, refund amounts exceeding the agent's approval threshold, customers who are demanding a refund and threatening to dispute the charge, requests involving policy exceptions, VIP customer complaints, or any situation where the customer mentions wanting to "speak to a manager" or "escalate" their issue. Also activate when processing a refund or return that does not meet standard eligibility criteria but the customer presents a compelling case for an exception. This skill manages the handoff process to ensure nothing falls through the cracks during escalation.

## Steps
1. Acknowledge the customer's frustration and assure them their concern is being taken seriously.
2. Classify the escalation type to route to the correct team:
   - **Refund exception**: Amount over $500 or outside return window — route to Finance Lead.
   - **Policy override**: Request contradicts published policy — route to Senior Support Manager.
   - **VIP complaint**: Customer is flagged as high-value account — route to VIP Relations.
   - **Dispute risk**: Customer mentions chargeback or legal action — route to Disputes Team.
3. Document the full interaction history and customer's specific request in the escalation ticket.
4. Include all relevant order details, previous interactions, and what resolution the customer is seeking.
5. Set the ticket priority based on urgency: P1 for dispute threats, P2 for VIP, P3 for standard exceptions.
6. Notify the customer that their case has been escalated and provide them with the escalation ticket number.
7. Set expectations for response time: P1 within 4 hours, P2 within 24 hours, P3 within 48 hours.
8. Add any agent notes about recommended resolution based on the customer's situation.
9. Transfer the live conversation if the customer is currently on chat or phone and a manager is available.

## Output Format
A text summary for the customer confirming the escalation, including the ticket number, the team handling their case, and the expected response time. Internally, a structured escalation note is attached to the ticket with all context needed for the receiving team.

## Common Pitfalls
- Escalating without gathering enough context, forcing the manager to re-ask questions the customer already answered.
- Not setting clear expectations for the customer about response time, leading to repeated follow-ups.
- Misclassifying the escalation type, which routes the ticket to the wrong team and delays resolution.
- Forgetting to include the customer's preferred resolution in the escalation notes.
