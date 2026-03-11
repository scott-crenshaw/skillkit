---
name: handle_refund
description: "Process customer refund requests by verifying purchase history, validating refund eligibility, and issuing the appropriate refund to the original payment method."
output_format: text
domain: customer_support
status: active
domain_areas:
  - Customer Service
task_types:
  - Analyze
  - Recommend
version: "1.0"
author: cs_team
tags:
  - refund
  - billing
  - returns
---

# Handle Refund

## When to Use
Use this skill when a customer contacts support requesting a refund or return for a product or service they purchased. This includes situations where the customer is unhappy with their purchase, received a defective item, was charged incorrectly, or wants to return an item within the return window. Activate this skill when the customer mentions words like "refund," "money back," "return," "charged wrong," or "cancel my order." This skill handles straightforward refund processing where the request falls within standard policy guidelines and does not require managerial escalation or exception handling.

## Steps
1. Greet the customer and acknowledge their refund request with empathy.
2. Look up the customer's order using their account ID, email address, or order number.
3. Verify the purchase details including date, amount, item description, and payment method.
4. Check the refund eligibility criteria against company policy:
   - Is the request within the 30-day return window?
   - Is the item in the eligible category (not final sale, digital goods, or custom orders)?
   - Has the customer already received a refund for this order?
5. If eligible, calculate the refund amount accounting for any partial usage, restocking fees, or promotional discounts that were applied.
6. Process the refund to the original payment method and provide the customer with a confirmation number.
7. Inform the customer of the expected timeline for the refund to appear (3-5 business days for credit cards, 5-10 for bank transfers).
8. Offer alternatives if appropriate, such as store credit or exchange, which may be faster.
9. Document the interaction in the CRM with the reason code, refund amount, and resolution.

## Output Format
A plain text response to the customer confirming the refund details, including the refund amount, the payment method being credited, the expected timeline, and a confirmation or reference number for their records.

## Common Pitfalls
- Forgetting to check if a refund was already issued for the same order, leading to duplicate refunds.
- Not accounting for promotional discounts when calculating the refund amount, which can result in over-refunding.
- Missing the return window cutoff by not checking the original purchase date first.
- Failing to document the interaction, which causes confusion if the customer calls back.
