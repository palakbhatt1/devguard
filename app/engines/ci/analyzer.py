from app.engines.ci.classifier import classify_ci_failure_rules
from app.engines.ci.log_cleaner import clean_ci_log
from app.llm.base import BaseLLMClient
from app.llm.prompts import CI_ANALYZER_SYSTEM_PROMPT, CI_ANALYZER_USER_PROMPT
from app.llm.schemas import CIFailureAnalysisResult


class CIFailureAnalyzer:
    """CI Failure Analyzer engine combining log cleaner, rule classifier, and LLM analysis."""

    def __init__(self, llm_client: BaseLLMClient):
        self.llm_client = llm_client

    async def analyze_log(
        self,
        raw_log: str,
        workflow_name: str = "CI Workflow",
        job_name: str = "build-and-test",
    ) -> CIFailureAnalysisResult:
        """Clean raw CI log, classify via rules, and request structured LLM root-cause analysis."""
        cleaned_log = clean_ci_log(raw_log)
        pre_class = classify_ci_failure_rules(cleaned_log)

        user_prompt = (
            CI_ANALYZER_USER_PROMPT
            .replace("{pre_classification}", str(pre_class))
            .replace("{workflow_name}", str(workflow_name))
            .replace("{job_name}", str(job_name))
            .replace("{cleaned_log}", str(cleaned_log))
        )

        try:
            res: CIFailureAnalysisResult = await self.llm_client.generate_structured(
                system_prompt=CI_ANALYZER_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                response_model=CIFailureAnalysisResult,
            )
            return res
        except Exception as e:
            # Fallback to rule pre-classification if LLM fails
            err_line = ""
            for line in cleaned_log.splitlines():
                if any(kw in line.lower() for kw in ["failed", "error", "exception", "exit code"]):
                    err_line = line.strip()
                    break

            root_cause = f"Category '{pre_class}' detected."
            if err_line:
                root_cause += f" Trigger line: '{err_line}'"

            fix = f"Investigate '{pre_class}' error in {job_name}. Inspect tracebacks and fix broken assertions or environment."

            return CIFailureAnalysisResult(
                failure_category=pre_class,
                root_cause=root_cause,
                suggested_fix=fix,
                confidence=0.7,
            )

