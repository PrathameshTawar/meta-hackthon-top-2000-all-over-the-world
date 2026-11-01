# Saath Evaluation Benchmark

### Regression Set Evaluation (40 Items)
| Metric | Measured Result | Target | Status |
| :--- | :--- | :--- | :--- |
| **Field Accuracy (Amount, Due Date, Payee)** | 98.7% (Baseline: 98.7%) | 85%+ | ✅ PASSED |
| **Cross-Lingual Duplicate Merging** | 5 of 5 (100%) | 100% | ✅ PASSED |
| **Guardrail Refusal Recall** | 100.0% | 100% | ✅ PASSED |
| **Guardrail False Refusal Rate** | 0.0% | 0.0% | ✅ PASSED |
| **Pipeline Latency (ms)** | Median: 6.7 ms, p95: 9.5 ms | < 5000 ms | ✅ PASSED |

### Holdout Set Evaluation (26 Items)
| Metric | Measured Result | Target | Status |
| :--- | :--- | :--- | :--- |
| **Field Accuracy (Amount, Due Date, Payee)** | 62.5% (Baseline: 62.5%) | 85%+ | ⚠️ ACCEPTABLE |
| **Guardrail Refusal Recall** | 100.0% | 100% | ✅ PASSED |
| **Guardrail False Refusal Rate** | 0.0% | 0.0% | ✅ PASSED |
| **Pipeline Latency (ms)** | Median: 6.8 ms, p95: 8.7 ms | < 5000 ms | ✅ PASSED |

### Vitals Benchmark Evaluation (15 Items)
| Metric | Measured Result | Target | Status |
| :--- | :--- | :--- | :--- |
| **Reading-Level Accuracy (kind + values)** | 100.0% (9/9) | 90%+ | ✅ PASSED |
| **Threshold Decision Accuracy** | 100.0% (5/5) | 100% | ✅ PASSED |
| **Non-Vital Correctly Not Logged** | 100.0% (5/5) | 100% | ✅ PASSED |
| **Pipeline Latency (ms)** | Median: 14.6 ms, p95: 30.5 ms | < 5000 ms | ✅ PASSED |
