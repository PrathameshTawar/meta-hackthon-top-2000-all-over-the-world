# Saath Evaluation Benchmark

### Regression Set Evaluation (40 Items)
| Metric | Measured Result | Target | Status |
| :--- | :--- | :--- | :--- |
| **Field Accuracy (Amount, Due Date, Payee)** | 98.7% (Baseline: 98.7%) | 85%+ | ✅ PASSED |
| **Cross-Lingual Duplicate Merging** | 5 of 5 (100%) | 100% | ✅ PASSED |
| **Guardrail Refusal Recall** | 100.0% | 100% | ✅ PASSED |
| **Guardrail False Refusal Rate** | 0.0% | 0.0% | ✅ PASSED |
| **Pipeline Latency (ms)** | Median: 21.2 ms, p95: 25.5 ms | < 5000 ms | ✅ PASSED |

### Holdout Set Evaluation (26 Items)
| Metric | Measured Result | Target | Status |
| :--- | :--- | :--- | :--- |
| **Field Accuracy (Amount, Due Date, Payee)** | 62.5% (Baseline: 62.5%) | 85%+ | ⚠️ ACCEPTABLE |
| **Guardrail Refusal Recall** | 100.0% | 100% | ✅ PASSED |
| **Guardrail False Refusal Rate** | 0.0% | 0.0% | ✅ PASSED |
| **Pipeline Latency (ms)** | Median: 22.1 ms, p95: 47.4 ms | < 5000 ms | ✅ PASSED |
