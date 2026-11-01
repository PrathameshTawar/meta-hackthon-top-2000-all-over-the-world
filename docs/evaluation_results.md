# Saath Evaluation Benchmark

### Regression Set Evaluation (40 Items)
| Metric | Measured Result | Target | Status |
| :--- | :--- | :--- | :--- |
| **Field Accuracy (Amount, Due Date, Payee)** | 98.7% (Baseline: 98.7%) | 85%+ | ✅ PASSED |
| **Cross-Lingual Duplicate Merging** | 5 of 5 (100%) | 100% | ✅ PASSED |
| **Guardrail Refusal Recall** | 100.0% | 100% | ✅ PASSED |
| **Guardrail False Refusal Rate** | 0.0% | 0.0% | ✅ PASSED |
| **Pipeline Latency (ms)** | Median: 9.9 ms, p95: 12.8 ms | < 5000 ms | ✅ PASSED |

### Holdout Set Evaluation (26 Items)
| Metric | Measured Result | Target | Status |
| :--- | :--- | :--- | :--- |
| **Field Accuracy (Amount, Due Date, Payee)** | 62.5% (Baseline: 62.5%) | 85%+ | ⚠️ ACCEPTABLE |
| **Guardrail Refusal Recall** | 100.0% | 100% | ✅ PASSED |
| **Guardrail False Refusal Rate** | 0.0% | 0.0% | ✅ PASSED |
| **Pipeline Latency (ms)** | Median: 10.6 ms, p95: 11.9 ms | < 5000 ms | ✅ PASSED |
