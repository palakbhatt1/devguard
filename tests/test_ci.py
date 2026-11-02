import pytest
from app.engines.ci import CIFailureAnalyzer, classify_ci_failure_rules, clean_ci_log
from app.llm import MockLLMClient


def test_clean_ci_log():
    raw = "\x1b[31m2024-03-30T10:00:00.123Z Error occurred\x1b[0m"
    cleaned = clean_ci_log(raw)
    assert "\x1b" not in cleaned
    assert "2024-03-30T" not in cleaned
    assert "Error occurred" in cleaned


def test_classify_ci_failure_rules():
    log_pytest = "FAILED tests/test_main.py::test_api - AssertionError: 500 != 200"
    assert classify_ci_failure_rules(log_pytest) == "failing_test"

    log_pip = "ERROR: Could not find a version that satisfies the requirement requests==9.9.9"
    assert classify_ci_failure_rules(log_pip) == "dependency_install"

    log_lint = "app/main.py:4:1: F401 'os' imported but unused"
    assert classify_ci_failure_rules(log_lint) == "lint_error"


@pytest.mark.anyio
async def test_ci_failure_analyzer():
    test_llm = MockLLMClient()
    analyzer = CIFailureAnalyzer(llm_client=test_llm)

    log_text = "pytest tests/\nFAILED tests/test_app.py - AssertionError"
    analysis = await analyzer.analyze_log(log_text)

    assert analysis.failure_category == "failing_test"
    assert analysis.root_cause is not None
    assert analysis.suggested_fix is not None
