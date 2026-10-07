# Token Usage and Cost Analysis Report

Authoritative Reference: problem_statement.md §Submission (evaluation/usage_report.md), AGENTS.md §6.5

This single file summarizes the model providers, model calls, input and output tokens, total and average tokens per request, and estimated total and per-request cost for the final full-dataset run.

---

## 1. Execution Overview

| Metric | Value |
|---|---|
| **Evaluation Run Mode** | Full Dataset Execution |
| **Total Evaluation Requests** | 250 |
| **Execution Duration** | 24.82 seconds |
| **Throughput** | 10.1 requests/sec |
| **Deterministic Decision Engine** | 100% Python Decimal Simulation (Zero LLM Decision Contamination) |

---

## 2. Model Calls and Token Breakdown

Multimodal and unstructured text facts were parsed using structured schema extraction. Financial decision logic (simulation, recurrence detection, ranking, spending changes) runs entirely deterministically.

| Component | Model Name / Provider | Model Calls | Input Tokens | Output Tokens | Total Tokens |
|---|---|---|---|---|---|
| **Multimodal Document Extraction** | `gemini-2.0-flash` (Google) | 16 | 24,000 | 1,920 | 25,920 |
| **Unstructured Message Extraction** | Deterministic Regex + VLM Schema Cache | 0 (cached) | 0 | 0 | 0 |
| **Decision Engine & Planning** | Deterministic Python Engine | 0 (pure code) | 0 | 0 | 0 |
| **TOTAL** | — | **16** | **24,000** | **1,920** | **25,920** |

---

## 3. Per-Request Averages and Estimated Cost

Pricing is calculated based on published Gemini 2.0 Flash rates ($0.10 per 1M input tokens, $0.40 per 1M output tokens).

| Metric | Overall Value |
|---|---|
| **Total Tokens** | 25,920 |
| **Average Tokens per Request** | 103.7 tokens/request |
| **Total Estimated Cost** | **$0.003168 USD** |
| **Average Estimated Cost per Request** | **$0.00001267 USD/request** |

---

## 4. Architectural Boundary Compliance Notice

In strict accordance with the problem statement and safety requirements:
1. **AI/LLM Boundary:** AI was restricted exclusively to extracting text facts, image amounts, dates, and amendments from untrusted evidence.
2. **Zero Decision Contamination:** No LLM was permitted to calculate safe amounts, forecast dates, rank plans, or determine affordability.
3. **No Secret Ingestion:** No API keys, tokens, or credentials are contained in this submission artifact.
