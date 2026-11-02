import pytest
from app.engines.errors import ErrorExplainer, parse_python_traceback
from app.llm import MockLLMClient


def test_parse_python_traceback():
    tb_text = """Traceback (most recent call last):
  File "app/main.py", line 42, in index
    result = divide(10, 0)
  File "app/utils.py", line 12, in divide
    return a / b
ZeroDivisionError: division by zero"""

    parsed = parse_python_traceback(tb_text)
    assert parsed.exception_type == "ZeroDivisionError"
    assert parsed.exception_message == "division by zero"
    assert parsed.failing_file == "app/utils.py"
    assert parsed.failing_line == 12


@pytest.mark.anyio
async def test_error_explainer():
    test_llm = MockLLMClient()
    explainer = ErrorExplainer(llm_client=test_llm)

    tb_text = """Traceback (most recent call last):
  File "app/main.py", line 10, in run
    val = data['user_id']
KeyError: 'user_id'"""

    res = await explainer.explain_error(tb_text)
    assert res.exception_type == "KeyError"
    assert res.summary is not None
    assert res.root_cause is not None
    assert res.suggested_fix is not None
