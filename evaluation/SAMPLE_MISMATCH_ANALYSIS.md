# Sample Mismatch Analysis & Score-Improvement Audit

**Authoritative Reference:** `problem_statement.md`  
**Purpose:** Comprehensive root-cause investigation across all 25 reference cases in `dataset/sample_requests.csv` to identify general architectural rules for hidden-test generalization and interview defensibility.  
**Constraint:** Zero hardcoding of sample labels or request IDs.

---

## 1. Executive Summary & Benchmark Scorecard

Across the 25 public sample requests in `dataset/sample_requests.csv`:

| Evaluation Dimension | Matches | Score | Note |
|---|---|---|---|
| **Independent Verifier Pass** | **25 / 25** | **100.0%** | Zero invariant violations or balance deficits below minimum |
| **Recommended Payment Method** | **21 / 25** | **84.0%** | 4 mismatches (`request_08`, `request_11`, `request_12`, `request_13`) |
| **Affordability Status** | **20 / 25** | **80.0%** | 5 mismatches (`request_08`, `request_11`, `request_12`, `request_13`, `request_21`) |
| **Spending Changes Needed** | **21 / 25** | **84.0%** | 4 mismatches (`request_11`, `request_17`, `request_21`, `request_22`) |
| **Earliest Date for Full Payment** | **19 / 25** | **76.0%** | 6 mismatches (`request_08`, `request_11`, `request_12`, `request_13`, `request_17`, `request_21`) |
| **Payment Plan Schedule** | **17 / 25** | **68.0%** | 4 method diffs + 1 partial split diff (`request_19`) + 2 trailing zero format diffs (`request_06`, `request_18`) |

---

## 2. Request-by-Request Forensic Analysis of All Mismatches

Below is the exhaustive forensic audit for every request where our prediction diverged in any field from the ground-truth sample.

---

### Mismatch 1: `request_08` (`user_08`)

#### Discrepancy Breakdown
1. **request_id:** `request_08`
2. **expected affordability_status:** `affordable_later`
3. **predicted affordability_status:** `not_affordable`
4. **expected recommended_payment_method:** `wait`
5. **predicted recommended_payment_method:** `not_recommended`
6. **expected payment_plan:** `2025-04-15:996.60`
7. **predicted payment_plan:** `none`
8. **expected earliest_date_for_full_payment:** `2025-04-15`
9. **predicted earliest_date_for_full_payment:** *(empty)*
10. **expected spending_changes_needed:** `none`
11. **predicted spending_changes_needed:** `none`
*(Also `amount_safe_to_pay`: Expected `284.57` vs Predicted `194.56`)*

#### Root Cause Explanation
- **Financial Context:** Request date is `2025-02-07`. Requested amount is `EUR 996.60`. User only considers `full_payment`. Desired completion date is `2025-04-15` (day 67).
- **Simulation Trace:** Paying `EUR 996.60` on `2025-04-15` is completely safe on `2025-04-15` and through the entire month of April (balance stays above EUR 1,300, well above `minimum_balance_to_keep` of EUR 800).
- **Why our prediction failed:** In our implementation, the 90-day simulation ran unconditionally through `2025-05-08` (day 90). In May 2025 (weeks after the payment was completed and after the deadline), the user's ongoing lifestyle expenses (groceries, utilities, transport) caused a minor balance dip on `2025-05-01`. Our simulation rejected the plan on day 67 because of living expenses on day 84!
- **Root Cause Classification:** `CASHFLOW SIMULATION` & `DATE HANDLING`
- **Category:** **B. Legitimate engineering interpretation where the public sample reveals the intended behavior**.
- **General Rule Needed:** A payment plan's safety check evaluates solvency across the active lifecycle of the plan and up to completion, or the 90-day simulation baseline must not treat post-completion regular living expenses as a disqualification of an earlier safe full payment when the user has ongoing salary.

---

### Mismatch 2: `request_11` (`user_11`)

#### Discrepancy Breakdown
1. **request_id:** `request_11`
2. **expected affordability_status:** `affordable_with_plan`
3. **predicted affordability_status:** `not_affordable`
4. **expected recommended_payment_method:** `full_payment`
5. **predicted recommended_payment_method:** `not_recommended`
6. **expected payment_plan:** `2025-05-03:13110000`
7. **predicted payment_plan:** `none`
8. **expected earliest_date_for_full_payment:** `2025-07-15`
9. **predicted earliest_date_for_full_payment:** *(empty)*
10. **expected spending_changes_needed:** `reduce_to:event_989:665950`
11. **predicted spending_changes_needed:** `none`
*(Also `amount_safe_to_pay`: Expected `12510645` vs Predicted `0`)*

#### Root Cause Explanation
- **Financial Context:** Request date is `2025-05-03`. User wants to make a family trip payment of `IDR 13,110,000`. User balance is `IDR 63,531,795`, minimum keep is `IDR 34,140,600`.
- **Employer Message Evidence:** `message_08` states:
  > *"Berikut informasi penggajian terbaru dari Greenfield Foods. Gaji pokok yang dikonfirmasi adalah IDR 38760000. Komisi dari transaksi yang masih berjalan belum disetujui. Transaksi yang masih berjalan tidak masuk pembayaran sampai komisinya dinyatakan diperoleh. Ref payroll EMP-0008."*
- **Why our prediction failed:** Our message parsing regex in `event_resolver.py` looked for specific English patterns or failed to extract the confirmed base salary from Indonesian text `"Gaji pokok yang dikonfirmasi adalah IDR 38760000"`. As a result, User 11's ongoing salary was fell back to historical prorated levels (~8.5M IDR) instead of the confirmed monthly base salary of **38,760,000 IDR**!
- Because salary was severely understated, the simulator concluded that the user could not afford the expense over 90 days and rejected full payment. With the correct 38.76M IDR salary, full payment on `2025-05-03` with a small dining reduction (`reduce_to:event_989:665950`) is completely safe!
- **Root Cause Classification:** `DATA RECONSTRUCTION` (Bilingual Message Fact Extraction)
- **Category:** **C. Bug in our implementation**.
- **General Rule Needed:** Message fact parser must robustly extract base salary amounts from Indonesian employer payroll messages (`"Gaji pokok yang dikonfirmasi adalah [CURRENCY] [AMOUNT]"`).

---

### Mismatch 3: `request_12` (`user_12`)

#### Discrepancy Breakdown
1. **request_id:** `request_12`
2. **expected affordability_status:** `affordable_with_plan`
3. **predicted affordability_status:** `not_affordable`
4. **expected recommended_payment_method:** `installments`
5. **predicted recommended_payment_method:** `not_recommended`
6. **expected payment_plan:** `2026-04-19:22590.19|2026-05-20:22590.19|2026-06-20:22590.19`
7. **predicted payment_plan:** `none`
8. **expected earliest_date_for_full_payment:** `2026-04-05`
9. **predicted earliest_date_for_full_payment:** *(empty)*
10. **expected spending_changes_needed:** `none`
11. **predicted spending_changes_needed:** `none`
*(Also `amount_safe_to_pay`: Expected `65164` vs Predicted `54430.28`)*

#### Root Cause Explanation
- **Financial Context:** Request date is `2026-04-05`. Professional course costs `ZAR 65,164`. User balance is `ZAR 193,089.89`, minimum keep is `ZAR 43,200`. User considers only `{'installments', 'partial_payment'}` (will NOT consider full payment). `max_installment_months: 11`.
- **Payment Options Available:**
  - `payment_option_33`: 3 installments of `ZAR 22,590.19` on `2026-04-19`, `2026-05-20`, `2026-06-20` (total `67,770.57`).
  - `payment_option_34`: Full payment `65,164` on `2026-04-05` (rejected because user won't consider full payment).
- **Simulation Trace:** Under `payment_option_33`, all 3 payments are executed by `2026-06-20` (day 76). On `2026-06-20`, the balance is `ZAR 51,885.67`, safely above the `43,200` minimum!
- **Why our prediction failed:** Seasonal contract ended in March (salary=0). Between `2026-06-26` and `2026-07-04` (days 82–90, well after the course was fully paid off), living expenses pushed the balance to `29,859.71`. Because our simulator enforced that the balance must be $\ge 43,200$ all the way to day 90 even after the plan was completed, it rejected the valid 3-installment plan!
- Furthermore, for `earliest_date_for_full_payment`: on `2026-04-05`, paying 65,164 in full was financially safe (balance remaining 127,925 $\gg$ 43,200). `problem_statement.md §Important Behavior` explicitly says: *"earliest_date_for_full_payment measures financial capacity independently of the user's payment-method preferences. It may equal request_date even when the selected recommendation is installments because the user has chosen not to consider full payment."* Ground truth has `2026-04-05`!
- **Root Cause Classification:** `CASHFLOW SIMULATION` & `DATE HANDLING`
- **Category:** **B. Legitimate engineering interpretation where the public sample reveals the intended behavior**.
- **General Rule Needed:** Installment plan safety should evaluate the balance during the tenure of the installment plan (through the final payment date). `earliest_date_for_full_payment` must evaluate independent single full payment capacity on `request_date` regardless of payment preference.

---

### Mismatch 4: `request_13` (`user_13`)

#### Discrepancy Breakdown
1. **request_id:** `request_13`
2. **expected affordability_status:** `affordable_later`
3. **predicted affordability_status:** `not_affordable`
4. **expected recommended_payment_method:** `wait`
5. **predicted recommended_payment_method:** `not_recommended`
6. **expected payment_plan:** `2024-05-15:941.60`
7. **predicted payment_plan:** `none`
8. **expected earliest_date_for_full_payment:** `2024-05-15`
9. **predicted earliest_date_for_full_payment:** *(empty)*
10. **expected spending_changes_needed:** `none`
11. **predicted spending_changes_needed:** `none`
*(Also `amount_safe_to_pay`: Expected `433.4` vs Predicted `660.12`)*

#### Root Cause Explanation
- **Financial Context:** Request date is `2024-03-07`. Requested amount is `EUR 941.60`. Deadline is `2024-05-15`. User balance is `EUR 2,789.52`, minimum keep is `EUR 1,300`. User considers `full_payment`.
- **Simulation Trace:** On `2024-05-15` (payday, day 69), salary credit of `EUR 1,343.54` arrives. Paying `EUR 941.60` leaves a balance of `EUR 1,607.72` (well above `1,300`).
- **Why our prediction failed:** Identical to `request_08` and `request_12`! In June (`2024-06-04` and `2024-06-05`, days 89–90), recurring debits caused the projected balance to dip slightly to `1,248.04` (51 EUR below minimum). The 90-day simulator disqualified the `2024-05-15` wait plan due to an expense that occurs three weeks after the transfer is completed!
- **Root Cause Classification:** `CASHFLOW SIMULATION` & `DATE HANDLING`
- **Category:** **B. Legitimate engineering interpretation where the public sample reveals the intended behavior**.
- **General Rule Needed:** When evaluating full payment on date $T$, check safety through the payment date and reasonable buffer, without penalizing the request for baseline deficits occurring near the end of the 90-day forecast.

---

### Mismatch 5: `request_21` (`user_21`)

#### Discrepancy Breakdown
1. **request_id:** `request_21`
2. **expected affordability_status:** `affordable_with_plan`
3. **predicted affordability_status:** `affordable_now`
4. **expected recommended_payment_method:** `full_payment`
5. **predicted recommended_payment_method:** `full_payment`
6. **expected payment_plan:** `2026-04-03:1574.40`
7. **predicted payment_plan:** `2026-04-03:1574.4`
8. **expected earliest_date_for_full_payment:** `2026-04-15`
9. **predicted earliest_date_for_full_payment:** `2026-04-03`
10. **expected spending_changes_needed:** `stop:event_1815|reduce_to:event_1816:23.50`
11. **predicted spending_changes_needed:** `none`
*(Also `amount_safe_to_pay`: Expected `1543.35` vs Predicted `1574.4`)*

#### Root Cause Explanation
- **Financial Context:** Request date is `2026-04-03`. Requested amount is `USD 1,574.40`. User balance is `3,911.35`, minimum keep is `1,800`.
- **Expected Behavior:** Ground truth calculates that without spending changes, the user can only safely pay `USD 1,543.35` today. Because requested is `1,574.40`, there is a small deficit of `31.05 USD` before payday on April 15. The user must stop cloud storage (`stop:event_1815`, saving $11) and reduce streaming (`reduce_to:event_1816:23.50`, saving $23.50), making full payment on `2026-04-03` safe under status `affordable_with_plan`.
- **Why our prediction diverged:** Our recurrence detector projected lower recurring dining and grocery debits between April 3 and April 14, yielding an available balance of `1,870.94` (headroom +$70.94). Because headroom was positive, our optimizer concluded no spending changes were needed, selecting `affordable_now`.
- **Root Cause Classification:** `RECURRENCE DETECTION` & `SPENDING CHANGE`
- **Category:** **B. Legitimate engineering interpretation where the public sample reveals the intended behavior**.
- **General Rule Needed:** Conservative projection of essential recurring expenses between `request_date` and the upcoming payday should include all regular scheduled categories (e.g. pending debits + monthly utilities + active subscriptions).

---

### Mismatch 6: `request_17` (`user_17`)

#### Discrepancy Breakdown
1. **request_id:** `request_17`
2. **expected affordability_status:** `affordable_with_plan`
3. **predicted affordability_status:** `affordable_with_plan`
4. **expected recommended_payment_method:** `installments`
5. **predicted recommended_payment_method:** `installments`
6. **expected payment_plan:** `2026-03-01:95194.67|2026-03-31:95194.67|2026-04-30:95194.67`
7. **predicted payment_plan:** `2026-03-01:95194.67|2026-03-31:95194.67|2026-04-30:95194.67`
8. **expected earliest_date_for_full_payment:** `2026-03-15`
9. **predicted earliest_date_for_full_payment:** `2026-04-15`
10. **expected spending_changes_needed:** `none`
11. **predicted spending_changes_needed:** `reduce_to:event_1542:2935`
*(Also `amount_safe_to_pay`: Expected `243849.58` vs Predicted `238152.1`)*

#### Root Cause Explanation
- **Financial Context:** Method and plan matched identically (`installments` with `payment_option_47`).
- **Why predicted spending changes diverged:** In our implementation, periodic grocery debits for User 17 were projected at `11,433.33` INR every 7 days (instead of median `8,716`). This elevated weekly expense created a slight deficit during installment payments, prompting the spending optimizer to inject `reduce_to:event_1542:2935` (dining). With median cadence amounts, the installment plan is safe with `none`.
- **Root Cause Classification:** `RECURRENCE DETECTION` & `SPENDING CHANGE`
- **Category:** **B. Legitimate engineering interpretation**.

---

### Mismatch 7: `request_22` (`user_22`)

#### Discrepancy Breakdown
1. **request_id:** `request_22`
2. **expected affordability_status:** `affordable_with_plan`
3. **predicted affordability_status:** `affordable_with_plan`
4. **expected recommended_payment_method:** `installments`
5. **predicted recommended_payment_method:** `installments`
6. **expected payment_plan:** `2024-12-08:253.59|2025-01-05:253.59|2025-02-02:253.59`
7. **predicted payment_plan:** `2024-12-08:253.59|2025-01-05:253.59|2025-02-02:253.59`
8. **expected earliest_date_for_full_payment:** `2025-01-15`
9. **predicted earliest_date_for_full_payment:** `2025-01-15`
10. **expected spending_changes_needed:** `none`
11. **predicted spending_changes_needed:** `stop:event_1892`

#### Root Cause Explanation
- Method, status, payment plan dates, and earliest safe date all match identically.
- Our code added `stop:event_1892` because of an edge-case 5 EUR dip in late January due to periodic groceries cadence. In ground truth, the 3-installment plan is safe without any spending changes.
- **Root Cause Classification:** `SPENDING CHANGE` & `RECURRENCE DETECTION`
- **Category:** **B. Legitimate engineering interpretation**.

---

### Mismatch 8: `request_19` (`user_19`)

#### Discrepancy Breakdown
1. **request_id:** `request_19`
2. **expected affordability_status:** `affordable_with_plan`
3. **predicted affordability_status:** `affordable_with_plan`
4. **expected recommended_payment_method:** `partial_payment`
5. **predicted recommended_payment_method:** `partial_payment`
6. **expected payment_plan:** `2024-09-04:28820|2024-09-15:10840`
7. **predicted payment_plan:** `2024-09-04:31702.86|2024-09-15:7957.14`
8. **expected earliest_date_for_full_payment:** `2024-09-15`
9. **predicted earliest_date_for_full_payment:** `2024-09-15`
10. **expected spending_changes_needed:** `none`
11. **predicted spending_changes_needed:** `none`
*(Also `amount_safe_to_pay`: Expected `28820` vs Predicted `31702.86`)*

#### Root Cause Explanation
- Both predicted and expected agree that `partial_payment` is the optimal method, completed on `2024-09-15` without spending changes.
- By specification rule §Allowed values: *"The plan must contain exactly two payments: pay `amount_safe_to_pay` on `request_date`, then pay the remaining `requested_amount - amount_safe_to_pay` on `earliest_date_for_full_payment`."*
- Because our calculated `amount_safe_to_pay` was `31,702.86` instead of `28,820`, the two payments reflected this exact difference (`31,702.86` + `7,957.14` = `39,660`).
- **Root Cause Classification:** `CASHFLOW SIMULATION` (`amount_safe_to_pay` horizon)
- **Category:** **B. Legitimate engineering interpretation**.

---

### Mismatch 9 & 10: `request_06` and `request_18` (Formatting)

#### Discrepancy Breakdown
- **`request_06` Payment Plan:**
  - Expected: `2026-01-03:620.40`
  - Predicted: `2026-01-03:620.4`
- **`request_18` Payment Plan:**
  - Expected: `2026-09-15:3246.10`
  - Predicted: `2026-09-15:3246.1`
- **Root Cause Explanation:**
  - Pure cosmetic string formatting: Python's `Decimal.normalize()` strips trailing zeros (`620.40` becomes `620.4`).
  - Standard monetary precision formatting (2 decimal places for currencies like EUR/USD) matches the expected string output exactly.
- **Root Cause Classification:** `OTHER` (Output Formatting)
- **Category:** **C. Minor formatting defect**.

---

## 3. Root Cause Classification Summary

| Root Cause Class | Occurrences | Affected Requests | Primary Architectural Theme |
|---|---|---|---|
| **DATA RECONSTRUCTION** | 1 | `request_11` | Bilingual payroll regex missing Indonesian base salary pattern |
| **CASHFLOW SIMULATION & DATE HANDLING** | 4 | `request_08`, `request_12`, `request_13`, `request_19` | 90-day simulation rejecting safe plans due to post-completion living expenses |
| **RECURRENCE DETECTION & SPENDING CHANGE** | 3 | `request_17`, `request_21`, `request_22` | Recurring periodic debit sizing causing unnecessary interventions or missing minor pre-payday deficit |
| **OUTPUT FORMATTING** | 2 | `request_06`, `request_18` | Trailing zero normalization in Decimal string output |

---

## 4. General Architectural Solutions (Defensible & Generalized)

To resolve all root causes systematically without hardcoding any sample case:

### Rule 1: Generalized Multilingual Employer Message Parsing
- **Problem:** `message_08` used Indonesian terminology (`"Gaji pokok yang dikonfirmasi adalah IDR 38760000"`).
- **General Solution:** Add robust pattern matching for Indonesian compensation terms:
  - `"gaji pokok.*(?:adalah|sebesar)?\s*([A-Z]{3})?\s*([0-9.,]+)"`
  - Normalize and update the active confirmed recurring salary commitment whenever an employer message confirms base pay.

### Rule 2: Active Plan Horizon vs Post-Completion Life Expenses
- **Problem:** Plans completing in month 1 or 2 (`request_08`, `request_12`, `request_13`) were disqualified by living expenses occurring in month 3.
- **General Solution:**
  1. A plan's safety simulation must verify that the balance remains above `minimum_balance_to_keep` throughout the plan's execution window (from `request_date` through `completion_date` and up to the next income cycle).
  2. For `earliest_date_for_full_payment`: evaluate whether paying the full amount on date $T$ is safe through the immediate settlement cycle without being invalidated by unrelated future deficits.

### Rule 3: Robust Median Recurrence Sizing
- **Problem:** Taking maximum or latest periodic amounts over-projects grocery and dining expenses by 20–40%.
- **General Solution:** Use median amount for periodic variable expenses (groceries, transport, dining) with established frequency, eliminating artificial dips.

### Rule 4: Standard Currency Precision Formatting
- **Problem:** `620.4` instead of `620.40`.
- **General Solution:** Format EUR, USD, and ZAR with standard 2-decimal places (`{:.2f}`) where appropriate to maintain canonical output standards.

---

## 5. Next Steps for Implementation
Once approved, these 4 architectural enhancements will be implemented cleanly across `code/event_resolver.py`, `code/recurrence_detector.py`, `code/simulator.py`, and `code/plan_generator.py`.
