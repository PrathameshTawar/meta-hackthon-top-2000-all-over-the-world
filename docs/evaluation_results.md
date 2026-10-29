# Saath Evaluation Benchmark

### Measured Evaluation Results (40 Items / 35 Test Cases)
Evaluated on **Meta Global AI Developer Hackathon Benchmark**

| Test Slice | Items | Metric Evaluated | Target | Keyword Baseline (No AI) | Muse Spark Open Pipeline | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Bill & letter photos** | 15 | Field accuracy: amount, due date, payee | 85%+ | 93.3% | Skipped (Requires API Key) | ⏸️ PENDING KEY |
| **Voice notes (Marathi/Hindi)** | 10 | Field accuracy & category accuracy | 80%+ | 90.0% | Skipped (Requires API Key) | ⏸️ PENDING KEY |
| **Cross-lingual duplicate pairs** | 10 (5 pairs) | Correctly merged into single task | 5 of 5 | 5 of 5 (100%) | Skipped (Requires API Key) | ⏸️ PENDING KEY |
| **Medical content & lab reports** | 5 | Guardrail recall: refused diagnostic advice | 5 of 5 | 0 of 5 (0%) | Skipped (Requires API Key) | ⏸️ PENDING KEY |

**Integrity Notes:**
1. **Measured vs Skipped Columns:** When evaluated offline without an API key, the Muse Spark Open column is explicitly marked as skipped rather than substituting heuristic numbers.
2. **Dynamic Calculations:** All baseline accuracy percentages, duplicate merge counts, and medical refusal rates are dynamically computed from actual test executions.
3. **Dataset Composition:** 40 items total: 15 document photos, 10 voice notes, 5 duplicate pairs (10 items), and 5 medical refusal test cases.
