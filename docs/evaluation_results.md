# Saath Evaluation Benchmark

### Measured Evaluation Results (40 Items / 35 Test Cases)
Evaluated on **Meta Global AI Developer Hackathon Benchmark**  
*Dataset: All items evaluated as typed text (simulated photo-reading and transcript output).*

| Test Slice | Items | Metric Evaluated | Target | Keyword Baseline (No AI) | Saath Guardrail | Muse Spark Open Pipeline | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Bill & letter photos** | 15 | Field accuracy: amount, due date, payee | 85%+ | 97.8% | — | Pending (Requires API Key) | ⏸️ Pending |
| **Voice notes (Marathi/Hindi)** | 10 | Field accuracy & category accuracy | 80%+ | 96.7% | — | Pending (Requires API Key) | ⏸️ Pending |
| **Cross-lingual duplicate pairs** | 10 (5 pairs) | Correctly merged into single task | 5 of 5 | 5 of 5 (100%) | — | Pending (Requires API Key) | ⏸️ Pending |
| **Medical content & lab reports** | 5 | Guardrail recall: refused diagnostic advice | 5 of 5 | 0 of 5 (0% Refusal, 100% Leaked) | 5 of 5 (100% Refusal) | Pending (Requires API Key) | ⏸️ Pending |

**Integrity Notes:**
1. **Measured vs Pending Columns:** Until live evaluation against Baseten API key is run, the Muse Spark Open column is shown as Pending rather than reporting unverified numbers.
2. **Dynamic Calculations:** All baseline accuracy percentages, duplicate merge counts, and guardrail refusal rates are dynamically computed from actual test executions.
3. **Dataset Composition:** 40 items total: 15 document photos, 10 voice notes, 5 duplicate pairs (10 items), and 5 medical refusal test cases. All 40 items are currently typed text (simulated photo-reading and transcript output).
