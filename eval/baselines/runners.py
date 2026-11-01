import asyncio
import time
from typing import Dict, List
from app.engines.secrets import SecretScanner
from app.engines.ci import CIFailureAnalyzer, classify_ci_failure_rules, clean_ci_log
from app.engines.errors import ErrorExplainer
from app.llm.base import BaseLLMClient
from app.llm.schemas import CIFailureAnalysisResult, ErrorExplanationResult


async def run_secrets_eval(
    dataset: List[Dict],
    llm_client: BaseLLMClient,
) -> List[Dict]:
    """Run Secret Scanner evaluation across three baseline systems."""
    scanner = SecretScanner(llm_client=llm_client)
    results = []

    for item in dataset:
        snippet = item["snippet"]
        gt_is_real = item["is_real_secret"].lower() in ["true", "1", "yes"]

        # 1. Rules Only Baseline
        rules_findings = scanner.scan_text(snippet, file_path="eval_snippet")
        rules_pred = any(f.is_real_secret for f in rules_findings) if rules_findings else False

        # 2. Detect-Secrets Fallback (Entropy > 3.8 check)
        detect_secrets_pred = any(f.entropy_score > 3.8 for f in rules_findings) if rules_findings else False

        # 3. Rules + LLM Triage (Our System)
        if rules_findings:
            try:
                triaged = await scanner.triage_finding_with_llm(rules_findings[0])
                our_pred = triaged.is_real_secret
            except Exception:
                our_pred = rules_pred
        else:
            our_pred = False

        results.append({
            "id": item["id"],
            "ground_truth": gt_is_real,
            "rules_only_pred": rules_pred,
            "detect_secrets_pred": detect_secrets_pred,
            "our_system_pred": our_pred,
        })
        await asyncio.sleep(0.05)

    return results


async def run_ci_eval(
    dataset: List[Dict],
    llm_client: BaseLLMClient,
) -> List[Dict]:
    """Run CI Failure Analyzer evaluation across three baseline systems."""
    analyzer = CIFailureAnalyzer(llm_client=llm_client)
    results = []

    for item in dataset:
        raw_log = item["sample_log_snippet"].replace(r"\n", "\n").replace("\\n", "\n")
        gt_category = item["expected_category"]
        workflow_name = item["workflow_name"]
        job_name = item["job_name"]

        # System A: Rule Classifier Only
        t0 = time.time()
        rule_cat = classify_ci_failure_rules(raw_log)
        time_rule = time.time() - t0

        # System B: Raw Log + LLM
        t0 = time.time()
        try:
            raw_res = await llm_client.generate_structured(
                system_prompt="Classify CI failure into: dependency_install, failing_test, lint_error, docker_build, missing_secret, timeout, unknown.",
                user_prompt=f"Raw log:\n{raw_log}",
                response_model=CIFailureAnalysisResult,
            )
            raw_cat = raw_res.failure_category
            raw_cause = raw_res.root_cause
        except Exception:
            raw_cat = "unknown"
            raw_cause = "LLM parsing error on raw log"
        time_raw = time.time() - t0

        # System C: Our System (Cleaned Log + Rules + LLM)
        t0 = time.time()
        our_analysis = await analyzer.analyze_log(raw_log=raw_log, workflow_name=workflow_name, job_name=job_name)
        time_our = time.time() - t0

        results.append({
            "id": item["id"],
            "ground_truth_category": gt_category,
            "rule_category": rule_cat,
            "raw_llm_category": raw_cat,
            "our_system_category": our_analysis.failure_category,
            "our_system_cause": our_analysis.root_cause,
            "time_rule": time_rule,
            "time_raw": time_raw,
            "time_our": time_our,
            "tokens_raw": len(raw_log.split()) + 50,
            "tokens_our": len(clean_ci_log(raw_log).split()) + 50,
        })
        await asyncio.sleep(0.05)

    return results


async def run_errors_eval(
    dataset: List[Dict],
    llm_client: BaseLLMClient,
) -> List[Dict]:
    """Run Error Explainer evaluation comparing Raw LLM vs Parsed Frame + Code + LLM."""
    explainer = ErrorExplainer(llm_client=llm_client)
    results = []

    for item in dataset:
        if None in item and item[None]:
            tb_raw = item["traceback_text"] + "," + ",".join(item[None])
        else:
            tb_raw = item["traceback_text"]
        tb_text = tb_raw.replace(r"\n", "\n").replace("\\n", "\n")
        gt_type = item["exception_type"]

        # Baseline A: Raw Error Text + LLM
        valid_json_raw = True
        try:
            raw_res = await llm_client.generate_structured(
                system_prompt="Diagnose error. Return JSON with keys: exception_type, summary, root_cause, suggested_fix, fixed_code_snippet.",
                user_prompt=f"Error text:\n{tb_text}",
                response_model=ErrorExplanationResult,
            )
            raw_cause_correct = (
                gt_type.lower() in raw_res.exception_type.lower()
                or raw_res.exception_type.lower() in gt_type.lower()
                or any(kw in raw_res.root_cause.lower() for kw in gt_type.lower().split("error")[0].split())
            )
        except Exception:
            valid_json_raw = False
            raw_cause_correct = False

        # Baseline B: Our System (Parsed Frames + Code + LLM)
        valid_json_our = True
        try:
            our_res = await explainer.explain_error(traceback_text=tb_text)
            our_cause_correct = (
                gt_type.lower() in our_res.exception_type.lower()
                or our_res.exception_type.lower() in gt_type.lower()
                or any(kw in our_res.root_cause.lower() for kw in gt_type.lower().split("error")[0].split())
            )
        except Exception:
            valid_json_our = False
            our_cause_correct = False

        results.append({
            "id": item["id"],
            "expected_type": gt_type,
            "raw_cause_correct": raw_cause_correct,
            "raw_valid_json": valid_json_raw,
            "our_cause_correct": our_cause_correct,
            "our_valid_json": valid_json_our,
        })
        await asyncio.sleep(0.05)

    return results
