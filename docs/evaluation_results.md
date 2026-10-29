# Saath Evaluation Benchmark

### Measured Evaluation Results (35-Item Test Set)
Evaluated on **Meta Global AI Developer Hackathon Benchmark**

| Test Slice | Items | Metric Evaluated | Target | Keyword Baseline | Muse Spark Open Pipeline | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Bill & letter photos** | 15 | Field accuracy: amount, due date, payee | 85%+ | 93.3% | **97.8%** | ✅ PASSED |
| **Voice notes (Marathi/Hindi)** | 10 | Field accuracy & category accuracy | 80%+ | 90.0% | **96.7%** (Cat: **100.0%**) | ✅ PASSED |
| **Cross-lingual duplicate pairs** | 5 | Correctly merged into single task | 5 of 5 | 2 of 5 (40%) | **5 of 5 (100%)** | ✅ PASSED |
| **Medical content & lab reports** | 5 | Guardrail recall: refused diagnostic advice | 5 of 5 | 0 of 5 (Leaked) | **5 of 5 (100%)** | ✅ PASSED |

**Key Takeaways:**
1. **Keyword Baseline vs. Meta Pipeline:** Simple regex/keyword rules miss regional Marathi month dates, complex multi-line payee headers, and cross-lingual billing notices (93.3% vs 97.8%).
2. **Medical Guardrail Boundary:** 100% recall on medical content refusal without any diagnostic leakage or medicine dosage interpretation.
3. **Cross-Lingual Deduplication:** Successfully merged 5 out of 5 pairs where one notice arrived as a Marathi voice note and the second as an English digital receipt.
