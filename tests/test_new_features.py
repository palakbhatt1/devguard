import os
import pytest
from typer.testing import CliRunner

from cli.main import app as cli_app
from app.models.domain import Finding


@pytest.fixture
def runner():
    """Typer CLI Runner fixture."""
    return CliRunner()


# =====================================================================
# 1. CliRunner Tests
# =====================================================================

def test_cli_status(runner):
    """Test 'devguard status' command displays configuration panel."""
    result = runner.invoke(cli_app, ["status"])
    assert result.exit_code == 0
    assert "DevGuard Status" in result.output
    assert "Provider:" in result.output
    assert "RAG Backend:" in result.output


def test_cli_ask(runner):
    """Test 'devguard ask' queries the codebase and outputs an answer."""
    result = runner.invoke(cli_app, ["ask", "How does secret masking work?"])
    assert result.exit_code == 0
    assert "Answer" in result.output


def test_cli_ci_analyze(runner):
    """Test 'devguard ci-analyze' parses and classifies a sample CI log."""
    sample_log = "app/web/samples/test_failure.log"
    if os.path.exists(sample_log):
        result = runner.invoke(cli_app, ["ci-analyze", sample_log])
        assert result.exit_code == 0
        assert "CI Analysis" in result.output
        assert "failing_test" in result.output


def test_cli_eval(runner):
    """Test 'devguard eval' displays benchmark results."""
    result = runner.invoke(cli_app, ["eval"])
    assert result.exit_code == 0
    assert "Secrets" in result.output or "CI" in result.output


def test_cli_scan_staged(runner):
    """Test 'devguard scan --staged' handles git staging gracefully."""
    result = runner.invoke(cli_app, ["scan", "--staged"])
    # Should exit cleanly (either 0 for no changes or clean)
    assert result.exit_code in [0, 1]
    assert "staged" in result.output.lower() or "clean" in result.output.lower() or "no staged changes" in result.output.lower()


# =====================================================================
# 2. TestClient Tests for All Pages
# =====================================================================

def test_page_landing(client):
    """Test GET / renders the public landing page."""
    res = client.get("/")
    assert res.status_code == 200
    assert "AI DevGuard" in res.text
    assert "DevSecOps" in res.text


def test_page_dashboard_overview(client):
    """Test GET /dashboard renders the main telemetry overview."""
    res = client.get("/dashboard")
    assert res.status_code == 200
    assert "Secret Scanner Findings" in res.text
    assert "Export Findings (JSON)" in res.text


def test_page_ci_analyzer(client):
    """Test GET /dashboard/ci and GET /ci render the CI Failure Analyzer."""
    for path in ["/dashboard/ci", "/ci"]:
        res = client.get(path)
        assert res.status_code == 200
        assert "CI Failure Analyzer" in res.text


def test_page_errors_explainer(client):
    """Test GET /dashboard/errors and GET /errors render Error Explainer view."""
    for path in ["/dashboard/errors", "/errors"]:
        res = client.get(path)
        assert res.status_code == 200
        assert "Error Explainer" in res.text


def test_page_evaluation_benchmark(client):
    """Test GET /dashboard/evaluation and GET /evaluation render evaluation view with provider banner."""
    for path in ["/dashboard/evaluation", "/evaluation"]:
        res = client.get(path)
        assert res.status_code == 200
        assert "Evaluation Benchmark" in res.text
        assert "LLM Provider" in res.text
        assert "Benchmark Dataset" in res.text


def test_page_rag_assistant(client):
    """Test GET /dashboard/rag and GET /rag render RAG Codebase Assistant."""
    for path in ["/dashboard/rag", "/rag"]:
        res = client.get(path)
        assert res.status_code == 200
        assert "RAG Codebase Assistant" in res.text
        assert "Keyword RAG" in res.text


def test_export_findings_json_masked_only(client, db_session):
    """Test GET /dashboard/export/findings exports JSON with only masked values."""
    # Seed a test finding
    finding = Finding(
        file_path="config.py",
        line_number=10,
        rule_name="AWS Access Key ID",
        masked_value="AKIA****TEST",
        entropy_score=3.85,
        is_real_secret=True,
        is_false_positive=False,
        reasoning="Test AWS key",
        context_snippet='AWS_KEY = "AKIA1234567890TEST"',
    )
    db_session.add(finding)
    db_session.commit()

    res = client.get("/dashboard/export/findings")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 1

    item = next(f for f in data if f["rule_name"] == "AWS Access Key ID")
    assert item["masked_value"] == "AKIA****TEST"
    # Ensure unmasked secret is NOT in exported payload
    assert "AKIA1234567890TEST" not in str(data)


# =====================================================================
# 3. Regression Tests (Deduplication & False Positive Toggle)
# =====================================================================

def test_finding_false_positive_toggle_regression(client, db_session):
    """Regression test: toggling false-positive updates state cleanly with no duplicate/ghost row."""
    f = Finding(
        file_path="src/service.py",
        line_number=42,
        rule_name="Generic API Key",
        masked_value="sec_****1234",
        entropy_score=4.12,
        is_real_secret=True,
        is_false_positive=False,
        reasoning="Sample key",
        context_snippet='API_KEY = "sec_1234"',
    )
    db_session.add(f)
    db_session.commit()
    db_session.refresh(f)
    fid = f.id

    # 1. Toggle False Positive -> True
    res = client.post(f"/dashboard/findings/{fid}/toggle-false-positive")
    assert res.status_code == 200
    assert f'id="finding-row-{fid}"' in res.text
    assert "Undo FP" in res.text or "False Positive" in res.text

    db_session.refresh(f)
    assert f.is_false_positive is True

    # 2. Toggle back -> False
    res2 = client.post(f"/dashboard/findings/{fid}/toggle-fp")
    assert res2.status_code == 200
    assert f'id="finding-row-{fid}"' in res2.text
    assert "Mark FP" in res2.text

    db_session.refresh(f)
    assert f.is_false_positive is False

    # 3. Verify exactly 1 record exists in DB (no ghost row spawned)
    count = db_session.query(Finding).filter(Finding.id == fid).count()
    assert count == 1


def test_finding_deduplication(client, db_session, tmp_path):
    """Regression test: running dashboard scan updates existing findings instead of creating duplicates."""
    test_file = tmp_path / "secret_sample.py"
    test_file.write_text('API_KEY = "AKIAIOSFODNN7EXAMPLE"\n', encoding="utf-8")
    dir_path = str(tmp_path)

    # Initial scan
    res1 = client.post("/dashboard/scan", data={"path": dir_path})
    assert res1.status_code == 200

    count1 = db_session.query(Finding).filter(Finding.file_path == "secret_sample.py").count()
    assert count1 >= 1

    # Second scan of identical path
    res2 = client.post("/dashboard/scan", data={"path": dir_path})
    assert res2.status_code == 200

    count2 = db_session.query(Finding).filter(Finding.file_path == "secret_sample.py").count()
    # Deduplication guarantee: row count must not duplicate on re-scan
    assert count2 == count1


def test_ast_vs_raw_error_side_by_side(client):
    """Test /dashboard/explain generates side-by-side comparison (Without AST vs With AST)."""
    tb = (
        'Traceback (most recent call last):\n'
        '  File "app/math_utils.py", line 15, in calculate_rate\n'
        '    return total_score / count\n'
        'ZeroDivisionError: division by zero'
    )
    res = client.post("/dashboard/explain", data={"traceback_text": tb, "use_ast": "true"})
    assert res.status_code == 200
    # Both comparison columns must be present in response
    assert "Without AST" in res.text
    assert "With AST" in res.text
    assert "calculate_rate" in res.text or "ZeroDivisionError" in res.text
