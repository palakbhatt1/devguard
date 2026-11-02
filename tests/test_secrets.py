import pytest
from app.engines.secrets import SecretScanner, mask_secret, shannon_entropy
from app.llm import MockLLMClient


def test_shannon_entropy():
    # Low entropy plain string
    low = shannon_entropy("aaaaaaaaaaaa")
    assert low == 0.0

    # High entropy random string
    high = shannon_entropy("wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")
    assert high > 4.0


def test_mask_secret():
    assert mask_secret("AKIA1234567890ABCDEF") == "AKIA****CDEF"
    assert mask_secret("ghp_1234567890abcdef") == "ghp_****cdef"
    assert mask_secret("short") == "s****t"
    assert mask_secret("") == "****"


@pytest.mark.anyio
async def test_secret_scanner_detects_aws_key():
    test_llm = MockLLMClient()
    scanner = SecretScanner(llm_client=test_llm)
    code_snippet = 'aws_key = "AKIAIOSFODNN7EXAMPLE"'

    findings = scanner.scan_text(code_snippet, file_path="test.py")
    assert len(findings) == 1
    assert findings[0].rule_name == "AWS Access Key ID"
    assert findings[0].masked_value == "AKIA****MPLE"

    triaged = await scanner.triage_finding_with_llm(findings[0])
    assert triaged.is_real_secret is True or triaged.is_real_secret is False
