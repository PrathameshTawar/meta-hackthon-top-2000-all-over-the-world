# Saath Evaluation Benchmark

### Regression Set Evaluation (40 Items)
| Metric | Measured Result | Target | Status |
| :--- | :--- | :--- | :--- |
| **Field Accuracy (Amount, Due Date, Payee)** | 94.7% (Baseline: 96.0%) | 85%+ | ✅ PASSED |
| **Cross-Lingual Duplicate Merging** | 5 of 5 (100%) | 100% | ✅ PASSED |
| **Guardrail Refusal Recall** | 100.0% | 100% | ✅ PASSED |
| **Guardrail False Refusal Rate** | 0.0% | 0.0% | ✅ PASSED |
| **Pipeline Latency (ms)** | Median: 22.7 ms, p95: 29.0 ms | < 5000 ms | ✅ PASSED |

### Holdout Set Evaluation (26 Items)
| Metric | Measured Result | Target | Status |
| :--- | :--- | :--- | :--- |
| **Field Accuracy (Amount, Due Date, Payee)** | 89.6% (Baseline: 62.5%) | 85%+ | ✅ PASSED |
| **Guardrail Refusal Recall** | 100.0% | 100% | ✅ PASSED |
| **Guardrail False Refusal Rate** | 60.0% | 0.0% | ❌ FAILED |
| **Pipeline Latency (ms)** | Median: 23.6 ms, p95: 32.5 ms | < 5000 ms | ✅ PASSED |

### Vitals Benchmark Evaluation (15 Items)
| Metric | Measured Result | Target | Status |
| :--- | :--- | :--- | :--- |
| **Reading-Level Accuracy (kind + values)** | 100.0% (9/9) | 90%+ | ✅ PASSED |
| **Threshold Decision Accuracy** | 100.0% (5/5) | 100% | ✅ PASSED |
| **Non-Vital Correctly Not Logged** | 100.0% (5/5) | 100% | ✅ PASSED |
| **Pipeline Latency (ms)** | Median: 36.0 ms, p95: 91.0 ms | < 5000 ms | ✅ PASSED |
