# Plan Verification and Safety Audit Report

The PlanVerifier conducts an independent 90-day re-simulation and constraint verification pass for every prediction in the dataset.

## Verification Summary

- **Total Requests Evaluated:** 250
- **Passed All Constraints & Invariants:** 250 / 250 (100.0%)
- **Invariant Failures:** 0

## Invariant Verification Rules

1. **Monetary Boundary:** `0 <= amount_safe_to_pay <= requested_amount` for all records.
2. **Affordable Now Invariants:** Status `affordable_now` strictly requires `recommended_payment_method == 'full_payment'`, `spending_changes_needed == 'none'`, and `earliest_date_for_full_payment == request_date`.
3. **Partial Payment Invariants:** Exactly 2 payments summing to `requested_amount`. First payment is `amount_safe_to_pay` on `request_date`. Second payment on `earliest_date_for_full_payment` on or before `desired_completion_date`.
4. **Installment Invariants:** Follows exact option schedule from `request_payment_options.csv`, respecting `max_installment_months`.
5. **Spending Changes Invariants:** At most 3 non-conflicting interventions (`stop` or `reduce_to`) on flexible recurring expenses. Zero interventions on protected categories.
6. **90-Day Safety Re-simulation:** Independent daily balance progression ensuring $B(t) \ge \text{minimum\_balance\_to\_keep}$ for every day $t \in [0, 90]$.

## Invariant Warnings / Edge Case Log

All requests passed independent verification and 90-day safety re-simulation.
