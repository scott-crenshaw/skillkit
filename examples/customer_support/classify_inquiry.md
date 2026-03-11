---
name: classify_inquiry
description: "Classify incoming customer inquiries into predefined categories to enable efficient routing to the appropriate support team or automated workflow."
output_format: classification
domain: customer_support
status: active
domain_areas:
  - Customer Service
task_types:
  - Classify
version: "1.0"
author: cs_team
tags:
  - classification
  - routing
  - triage
---

# Classify Inquiry

## When to Use
Use this skill when a new customer inquiry arrives and needs to be categorized before it can be handled. This is typically the first skill activated in a support workflow, running on every incoming message to determine which specialized skill or team should handle the request. Activate on any new support ticket, chat message, or email that has not yet been classified. Do not use this skill if the inquiry has already been classified and routed.

## Steps
1. Read the full text of the customer's inquiry, including any subject line or metadata.
2. Identify primary intent keywords and phrases that map to known categories.
3. Assign the inquiry to one of the following categories:
   - **Billing**: charges, payments, invoices, refunds, subscriptions, pricing
   - **Technical Support**: bugs, errors, crashes, not working, setup, configuration
   - **Account Management**: password reset, login issues, profile updates, cancellation
   - **Product Information**: features, availability, compatibility, specifications
   - **Shipping & Delivery**: tracking, delivery status, lost package, address change
   - **Feedback & Complaints**: dissatisfied, complaint, suggestion, compliment
   - **General**: anything that doesn't fit the above categories
4. If the inquiry contains multiple intents, classify by the primary intent — the one the customer seems most urgent about.
5. Assign a confidence score to the classification based on keyword match strength and context clarity.
6. If confidence is below 70%, flag for human review rather than auto-routing.
7. Tag the inquiry with any secondary categories for tracking purposes.
8. Route the classified inquiry to the appropriate queue or trigger the matching skill.

## Output Format
A structured classification result containing the primary category, confidence score (0-100), any secondary categories, and the recommended routing destination or next skill to activate.

## Common Pitfalls
- Over-relying on single keywords without considering context (e.g., "charge" could be billing or technical).
- Failing to detect multi-intent messages and only addressing the secondary concern.
- Setting the confidence threshold too low, which leads to misrouted tickets.
- Not updating the category definitions as new product lines or support topics emerge.
