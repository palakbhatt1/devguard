# AI DevGuard Evaluation Rubric

## Research Question
*Does adding an LLM on top of rule-based parsing find secrets, explain errors, and identify CI failure root causes more accurately than rules alone or an LLM given raw input?*

---

## 1. Secret Scanning Evaluation Metrics
- **True Positive (TP)**: Real secret correctly flagged as real secret.
- **False Positive (FP)**: Decoy/placeholder incorrectly flagged as real secret.
- **False Negative (FN)**: Real secret missed or classified as placeholder.
- **True Negative (TN)**: Decoy/placeholder correctly identified as decoy.

### Formulae:
- $\text{Precision} = \frac{TP}{TP + FP}$
- $\text{Recall} = \frac{TP}{TP + FN}$
- $\text{F1 Score} = 2 \times \frac{\text{Precision} \times \text{Recall}}{\text{Precision} + \text{Recall}}$
- $\text{False Alarm Rate} = \frac{FP}{FP + TN}$

---

## 2. CI Failure Root-Cause Scoring Rubric (Human / LLM Evaluator)
When evaluating the generated root cause explanation against ground truth:

| Grade | Score | Criteria |
|---|---|---|
| **Yes (Full)** | `1.0` | Identifies the exact broken step, failing command, and underlying cause (e.g. missing dependency version or syntax error). |
| **Partly** | `0.5` | Identifies the failure category correctly but gives vague or incomplete technical details. |
| **No (Zero)** | `0.0` | Hallucinates incorrect cause, misses the failing step entirely, or attributes error to unrelated code. |

---

## 3. Error Explainer Metrics
- **Correct Cause Rate**: Percentage of tracebacks where LLM identifies the precise exception cause.
- **Valid JSON Rate**: Percentage of LLM responses that parse cleanly as valid Pydantic JSON schemas without syntax errors.
