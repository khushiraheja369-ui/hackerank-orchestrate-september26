# Sample Benchmark Results (25 Public Reference Requests)

This report audits the deterministic Buy or Wait? decision engine across all 25 public sample requests in `dataset/sample_requests.csv`.
In accordance with challenge constraints, **zero sample labels or request IDs are hardcoded** in the decision logic.

## Benchmark Summary

| Metric | Matches | Accuracy |
|---|---|---|
| **Recommended Payment Method** | **24 / 25** | **96.0%** |
| **Affordability Status** | **23 / 25** | **92.0%** |
| **Spending Changes Needed** | **23 / 25** | **92.0%** |
| **Payment Plan Schedule** | **23 / 25** | **92.0%** |
| **Earliest Safe Date** | **23 / 25** | **92.0%** |

## Request-by-Request Comparison Table

| Request ID | User | Pred Method | Exp Method | Method Match | Pred Changes | Exp Changes | Verifier Pass |
|---|---|---|---|---|---|---|---|
| `request_01` | `user_01` | full_payment | full_payment | MATCH | none | none | PASS |
| `request_02` | `user_02` | installments | installments | MATCH | none | none | PASS |
| `request_03` | `user_03` | wait | wait | MATCH | none | none | PASS |
| `request_04` | `user_04` | wait | wait | MATCH | none | none | PASS |
| `request_05` | `user_05` | not_recommended | not_recommended | MATCH | none | none | PASS |
| `request_06` | `user_06` | full_payment | full_payment | MATCH | stop:event_476 | stop:event_476 | PASS |
| `request_07` | `user_07` | installments | installments | MATCH | none | none | PASS |
| `request_08` | `user_08` | wait | wait | MATCH | none | none | PASS |
| `request_09` | `user_09` | full_payment | full_payment | MATCH | none | none | PASS |
| `request_10` | `user_10` | not_recommended | not_recommended | MATCH | none | none | PASS |
| `request_11` | `user_11` | wait | full_payment | DIFF | none | reduce_to:event_989:665950 | PASS |
| `request_12` | `user_12` | installments | installments | MATCH | none | none | PASS |
| `request_13` | `user_13` | wait | wait | MATCH | none | none | PASS |
| `request_14` | `user_14` | not_recommended | not_recommended | MATCH | none | none | PASS |
| `request_15` | `user_15` | not_recommended | not_recommended | MATCH | none | none | PASS |
| `request_16` | `user_16` | full_payment | full_payment | MATCH | none | none | PASS |
| `request_17` | `user_17` | installments | installments | MATCH | none | none | PASS |
| `request_18` | `user_18` | wait | wait | MATCH | none | none | PASS |
| `request_19` | `user_19` | partial_payment | partial_payment | MATCH | none | none | PASS |
| `request_20` | `user_20` | not_recommended | not_recommended | MATCH | none | none | PASS |
| `request_21` | `user_21` | full_payment | full_payment | MATCH | none | stop:event_1815|reduce_to:event_1816:23.50 | PASS |
| `request_22` | `user_22` | installments | installments | MATCH | none | none | PASS |
| `request_23` | `user_23` | wait | wait | MATCH | none | none | PASS |
| `request_24` | `user_24` | not_recommended | not_recommended | MATCH | none | none | PASS |
| `request_25` | `user_25` | not_recommended | not_recommended | MATCH | none | none | PASS |
