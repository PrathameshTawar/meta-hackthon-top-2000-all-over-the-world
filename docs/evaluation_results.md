# Saath Evaluation Benchmark

### Regression Set Evaluation (40 Items)
| Metric | Measured Result | Target | Status |
| :--- | :--- | :--- | :--- |
| **Field Accuracy (Amount, Due Date, Payee)** | 94.7% (Baseline: 96.0%) | 85%+ | ✅ PASSED |
| **Cross-Lingual Duplicate Merging** | 5 of 5 (100%) | 100% | ✅ PASSED |
| **Guardrail Refusal Recall** | 100.0% | 100% | ✅ PASSED |
| **Guardrail False Refusal Rate** | 0.0% | 0.0% | ✅ PASSED |
| **Pipeline Latency (ms)** | Median: 16927.9 ms, p95: 32638.7 ms | < 5000 ms | ✅ PASSED |

### Holdout Set Evaluation (26 Items)
| Metric | Measured Result | Target | Status |
| :--- | :--- | :--- | :--- |
| **Field Accuracy (Amount, Due Date, Payee)** | 89.6% (Baseline: 62.5%) | 85%+ | ✅ PASSED |
| **Guardrail Refusal Recall** | 100.0% | 100% | ✅ PASSED |
| **Guardrail False Refusal Rate** | 60.0% | 0.0% | ❌ FAILED |
| **Pipeline Latency (ms)** | Median: 13305.8 ms, p95: 55948.7 ms | < 5000 ms | ✅ PASSED |

### Vitals Benchmark Evaluation (15 Items)
| Metric | Measured Result | Target | Status |
| :--- | :--- | :--- | :--- |
| **Reading-Level Accuracy (kind + values)** | 100.0% (9/9) | 90%+ | ✅ PASSED |
| **Threshold Decision Accuracy** | 100.0% (5/5) | 100% | ✅ PASSED |
| **Non-Vital Correctly Not Logged** | 100.0% (5/5) | 100% | ✅ PASSED |
| **Pipeline Latency (ms)** | Median: 47.9 ms, p95: 35109.3 ms | < 5000 ms | ✅ PASSED |
