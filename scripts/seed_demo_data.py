"""Seed demo data into DevGuard DB for dashboard demo."""
import sys, os, asyncio

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, init_db
from app.models.domain import Finding, WorkflowAnalysis, ErrorExplanation

def seed():
    init_db()
    db = SessionLocal()
    try:
        # Clear existing
        db.query(Finding).delete()
        db.query(WorkflowAnalysis).delete()
        db.query(ErrorExplanation).delete()
        db.commit()

        # Seed Findings
        findings = [
            Finding(file_path="config/settings.py", line_number=12, rule_name="AWS Access Key ID",
                    masked_value="AKIA****CDEF", entropy_score=3.91, is_real_secret=True, is_false_positive=False,
                    reasoning="High entropy AWS AKIA prefix detected.", context_snippet='AWS_KEY = "AKIAIOSFODNN7EXAMPLE"'),
            Finding(file_path=".env.local", line_number=3, rule_name="Generic Secret Assignment",
                    masked_value="ghp_****ABCD", entropy_score=4.21, is_real_secret=True, is_false_positive=False,
                    reasoning="High entropy GitHub token pattern.", context_snippet='GITHUB_TOKEN = "ghp_mock_placeholder_token_devguard"'),
            Finding(file_path="tests/fixtures.py", line_number=7, rule_name="Generic Secret Assignment",
                    masked_value="your_****here", entropy_score=2.1, is_real_secret=False, is_false_positive=False,
                    reasoning="Known placeholder keyword detected.", context_snippet='API_KEY = "your_api_key_here"'),
            Finding(file_path="src/auth.py", line_number=22, rule_name="JSON Web Token (JWT)",
                    masked_value="eyJ****YzE", entropy_score=4.55, is_real_secret=True, is_false_positive=False,
                    reasoning="Valid JWT structure with high entropy payload.", context_snippet='token = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyMSJ9.abcde"'),
            Finding(file_path="deploy/docker-compose.yml", line_number=15, rule_name="Generic Secret Assignment",
                    masked_value="pass****123", entropy_score=2.8, is_real_secret=False, is_false_positive=True,
                    reasoning="Marked as false positive by user.", context_snippet='DB_PASSWORD = "password123"'),
            Finding(file_path="src/payments.py", line_number=8, rule_name="Generic Secret Assignment",
                    masked_value="sk_te****XYZ", entropy_score=4.1, is_real_secret=True, is_false_positive=False,
                    reasoning="Stripe test key format detected.", context_snippet='STRIPE_KEY = "sk_test_mock_token_placeholder"'),
        ]
        db.add_all(findings)

        # Seed CI Analyses
        ci_analyses = [
            WorkflowAnalysis(workflow_name="CI Pipeline", job_name="test", failure_category="failing_test",
                root_cause="pytest collected 3 failures in test_api.py due to missing authentication header in mock client.",
                suggested_fix="Add `Authorization: Bearer test_token` header to all test client requests in conftest.py.", confidence=0.95),
            WorkflowAnalysis(workflow_name="Build & Deploy", job_name="build", failure_category="dependency_install",
                root_cause="pip install failed: no matching distribution found for `fastapi==0.200.0`. Version does not exist.",
                suggested_fix="Pin `fastapi>=0.110.0,<0.120.0` in pyproject.toml dependencies.", confidence=0.92),
            WorkflowAnalysis(workflow_name="Lint Check", job_name="lint", failure_category="lint_error",
                root_cause="ruff check reported 4 violations: E501 line too long in scanner.py lines 45, 67, 89, 102.",
                suggested_fix="Run `ruff check --fix .` or set `line-length = 120` in pyproject.toml [tool.ruff].", confidence=0.98),
            WorkflowAnalysis(workflow_name="Docker Build", job_name="docker", failure_category="docker_build",
                root_cause="Dockerfile COPY step failed: source path `app/static/` does not exist in build context.",
                suggested_fix="Create the `app/static/` directory or update COPY instruction to match existing paths.", confidence=0.89),
            WorkflowAnalysis(workflow_name="Integration Tests", job_name="integration", failure_category="missing_secret",
                root_cause="GITHUB_TOKEN environment variable not set. GitHub API calls returning 401 Unauthorized.",
                suggested_fix="Add GITHUB_TOKEN to repository secrets and reference it in the workflow env section.", confidence=0.96),
        ]
        db.add_all(ci_analyses)

        # Seed Error Explanations
        errors = [
            ErrorExplanation(exception_type="ZeroDivisionError", summary="Division by zero in rate calculator",
                root_cause="The `count` variable is zero when `calculate_rate()` executes `total_score / count`.",
                suggested_fix="Add a guard: `if count == 0: return 0.0` before the division.",
                fixed_code_snippet="def calculate_rate(total_score, count):\n    if count == 0:\n        return 0.0\n    return total_score / count",
                file_path="app/math_utils.py", line_number=15),
            ErrorExplanation(exception_type="KeyError", summary="Missing key 'user_id' in request payload",
                root_cause="The `payload` dict does not contain the key `user_id` when the request is unauthenticated.",
                suggested_fix="Use `payload.get('user_id')` and validate before processing, or return 401 if missing.",
                fixed_code_snippet="user_id = payload.get('user_id')\nif not user_id:\n    raise HTTPException(status_code=401)",
                file_path="app/api/users.py", line_number=28),
        ]
        db.add_all(errors)
        db.commit()
        print("✅ Demo data seeded successfully!")
        print(f"   - {len(findings)} findings")
        print(f"   - {len(ci_analyses)} CI analyses")
        print(f"   - {len(errors)} error explanations")
    finally:
        db.close()

if __name__ == "__main__":
    seed()
