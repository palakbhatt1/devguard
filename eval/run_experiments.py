import asyncio
import csv
import json
import os
import sys
from datetime import datetime

# Ensure root workspace directory is in python path and stdout handles UTF-8
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from typing import Dict, List
from app.config import get_settings
from app.llm import get_llm_client, MockLLMClient
from eval.baselines.runners import run_ci_eval, run_errors_eval, run_secrets_eval


def load_csv_dataset(filepath: str) -> List[Dict]:
    """Load evaluation CSV dataset file into list of dictionaries."""
    if not os.path.exists(filepath):
        print(f"Error: Dataset file '{filepath}' not found.")
        sys.exit(1)
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def compute_secrets_metrics(results: List[Dict], pred_key: str) -> Dict[str, float]:
    """Calculate Precision, Recall, F1 Score, and False Alarm Rate."""
    tp = sum(1 for r in results if r["ground_truth"] and r[pred_key])
    fp = sum(1 for r in results if not r["ground_truth"] and r[pred_key])
    fn = sum(1 for r in results if r["ground_truth"] and not r[pred_key])
    tn = sum(1 for r in results if not r["ground_truth"] and not r[pred_key])

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    false_alarm_rate = fp / (fp + tn) if (fp + tn) > 0 else 0.0

    return {
        "precision": round(precision * 100, 2),
        "recall": round(recall * 100, 2),
        "f1": round(f1 * 100, 2),
        "false_alarm_rate": round(false_alarm_rate * 100, 2),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
    }


async def main():
    print("=" * 70)
    print("🛡️ AI DevGuard - Benchmark & Evaluation Suite")
    print("Research Question: Does adding an LLM on top of rule-based parsing")
    print("find secrets, explain errors, and identify CI failures more accurately?")
    print("=" * 70)

    settings = get_settings()
    llm_client = get_llm_client()
    is_mock = isinstance(llm_client, MockLLMClient)
    provider_name = "mock" if is_mock else settings.LLM_PROVIDER
    model_name = "offline-mock" if is_mock else (settings.LLM_MODEL or "gemini-3.1-flash-lite")
    tag = " (Mock)" if is_mock else f" ({provider_name})"

    print(f"Active Provider: {provider_name} | Model: {model_name}")

    eval_dir = os.path.dirname(os.path.abspath(__file__))

    # ---------------------------------------------------------
    # 1. Secrets Evaluation
    # ---------------------------------------------------------
    print("\n[1/3] Running Secret Scanner Benchmark (60 Labeled Snippets)...")
    secrets_dataset = load_csv_dataset(os.path.join(eval_dir, "datasets", "secrets", "labels.csv"))
    secrets_res = await run_secrets_eval(secrets_dataset, llm_client)

    m_rules = compute_secrets_metrics(secrets_res, "rules_only_pred")
    m_detect = compute_secrets_metrics(secrets_res, "detect_secrets_pred")
    m_our = compute_secrets_metrics(secrets_res, "our_system_pred")

    secrets_csv_path = os.path.join(eval_dir, "results_secrets.csv")
    with open(secrets_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["System", "Precision (%)", "Recall (%)", "F1 Score (%)", "False Alarm Rate (%)", "TP", "FP", "FN", "TN"])
        writer.writerow(["Rules Only", m_rules["precision"], m_rules["recall"], m_rules["f1"], m_rules["false_alarm_rate"], m_rules["tp"], m_rules["fp"], m_rules["fn"], m_rules["tn"]])
        writer.writerow(["Detect-Secrets Fallback", m_detect["precision"], m_detect["recall"], m_detect["f1"], m_detect["false_alarm_rate"], m_detect["tp"], m_detect["fp"], m_detect["fn"], m_detect["tn"]])
        writer.writerow([f"Rules + LLM Triage (Our System{tag})", m_our["precision"], m_our["recall"], m_our["f1"], m_our["false_alarm_rate"], m_our["tp"], m_our["fp"], m_our["fn"], m_our["tn"]])

    print(f"  -> Saved secrets evaluation results to '{secrets_csv_path}'")
    print(f"     * Rules Only: P={m_rules['precision']}%, R={m_rules['recall']}%, F1={m_rules['f1']}%, FAR={m_rules['false_alarm_rate']}%")
    print(f"     * Our System: P={m_our['precision']}%, R={m_our['recall']}%, F1={m_our['f1']}%, FAR={m_our['false_alarm_rate']}%")

    # ---------------------------------------------------------
    # 2. CI Failures Evaluation
    # ---------------------------------------------------------
    print("\n[2/3] Running CI Failure Analyzer Benchmark (30 Log Runs)...")
    ci_dataset = load_csv_dataset(os.path.join(eval_dir, "datasets", "ci_logs", "labels.csv"))
    ci_res = await run_ci_eval(ci_dataset, llm_client)

    acc_rule = sum(1 for r in ci_res if r["rule_category"] == r["ground_truth_category"]) / len(ci_res) * 100
    acc_raw = sum(1 for r in ci_res if r["raw_llm_category"] == r["ground_truth_category"]) / len(ci_res) * 100
    acc_our = sum(1 for r in ci_res if r["our_system_category"] == r["ground_truth_category"]) / len(ci_res) * 100

    ci_csv_path = os.path.join(eval_dir, "results_ci.csv")
    with open(ci_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["System", "Category Accuracy (%)", "Avg Time (s)", "Avg Tokens"])
        writer.writerow(["Rule Classifier Only", round(acc_rule, 2), round(sum(r["time_rule"] for r in ci_res)/len(ci_res), 4), 0])
        writer.writerow([f"Raw Log + LLM{tag}", round(acc_raw, 2), round(sum(r["time_raw"] for r in ci_res)/len(ci_res), 4), round(sum(r["tokens_raw"] for r in ci_res)/len(ci_res), 1)])
        writer.writerow([f"Cleaned Log + Rules + LLM (Our System{tag})", round(acc_our, 2), round(sum(r["time_our"] for r in ci_res)/len(ci_res), 4), round(sum(r["tokens_our"] for r in ci_res)/len(ci_res), 1)])

    print(f"  -> Saved CI evaluation results to '{ci_csv_path}'")
    print(f"     * Rule Classifier Only: Accuracy={acc_rule:.2f}%")
    print(f"     * Raw Log + LLM:       Accuracy={acc_raw:.2f}%")
    print(f"     * Our System:          Accuracy={acc_our:.2f}%")

    # ---------------------------------------------------------
    # 3. Errors Evaluation
    # ---------------------------------------------------------
    print("\n[3/3] Running Error Explainer Benchmark (25 Stack Traces with Strict Root-Cause Scorer)...")
    errors_dataset = load_csv_dataset(os.path.join(eval_dir, "datasets", "traces", "labels.csv"))
    errors_res = await run_errors_eval(errors_dataset, llm_client)

    raw_cause_rate = sum(1 for r in errors_res if r["raw_cause_correct"]) / len(errors_res) * 100
    raw_json_rate = sum(1 for r in errors_res if r["raw_valid_json"]) / len(errors_res) * 100
    our_cause_rate = sum(1 for r in errors_res if r["our_cause_correct"]) / len(errors_res) * 100
    our_json_rate = sum(1 for r in errors_res if r["our_valid_json"]) / len(errors_res) * 100

    errors_csv_path = os.path.join(eval_dir, "results_errors.csv")
    with open(errors_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["System", "Correct Cause Rate (%)", "Valid JSON Rate (%)"])
        writer.writerow([f"Raw Error Text + LLM{tag}", round(raw_cause_rate, 2), round(raw_json_rate, 2)])
        writer.writerow([f"Parsed Frame + Code + LLM (Our System{tag})", round(our_cause_rate, 2), round(our_json_rate, 2)])

    print(f"  -> Saved errors evaluation results to '{errors_csv_path}'")
    print(f"     * Raw Error Text + LLM: Cause Accuracy={raw_cause_rate:.2f}%, Valid JSON={raw_json_rate:.2f}%")
    print(f"     * Our System:          Cause Accuracy={our_cause_rate:.2f}%, Valid JSON={our_json_rate:.2f}%")

    # Save benchmark metadata
    meta = {
        "provider": provider_name,
        "model": model_name,
        "is_mock": is_mock,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "dataset_size": len(secrets_dataset) + len(ci_dataset) + len(errors_dataset),
        "secrets_count": len(secrets_dataset),
        "ci_count": len(ci_dataset),
        "errors_count": len(errors_dataset),
        "scorer": "strict_root_cause_keyword_matching",
    }
    meta_path = os.path.join(eval_dir, "eval_meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    # ---------------------------------------------------------
    # Failure Taxonomy Summary Report
    # ---------------------------------------------------------
    print("\n" + "=" * 70)
    print("📊 FAILURE TAXONOMY & LIMITATIONS SUMMARY")
    print("=" * 70)
    print("1. Secret Scanner:")
    print("   - Failure Type 1 (False Negative): Low-entropy keys matching standard prose (e.g. short tokens).")
    print("   - Failure Type 2 (False Positive): Hex/Base64 strings in compiled assets matching min entropy threshold.")
    print("2. CI Failure Analyzer:")
    print("   - Failure Type 1: Multi-stage pipeline cascading errors where root cause occurs earlier than failure step.")
    print("3. Error Explainer:")
    print("   - Failure Type 1: Complex meta-programming exceptions lacking local source lines on disk.")
    print("=" * 70)
    print(f"✅ Benchmark complete! All CSV tables and eval_meta.json generated successfully.")


if __name__ == "__main__":
    asyncio.run(main())
