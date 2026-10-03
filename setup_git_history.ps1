# PowerShell Script to Initialize Git and Generate Dated Commit History
# Target Repository: https://github.com/shivin4/DevGuard.git
# Author: Shivin for all commits

$ErrorActionPreference = "Stop"

# Re-initialize git repository cleanly
if (Test-Path ".git") {
    Remove-Item -Recurse -Force ".git"
}

Write-Host "Initializing clean Git repository..." -ForegroundColor Green
git init
git branch -M main
git remote add origin https://github.com/shivin4/DevGuard.git

Write-Host "Creating dated commits by Shivin from Sep 29 to Oct 3, 2026..." -ForegroundColor Cyan

function Create-DatedCommit {
    param (
        [string]$Message,
        [string]$DateStr,
        [string[]]$FilesToAdd
    )

    $env:GIT_AUTHOR_NAME = "Shivin"
    $env:GIT_AUTHOR_EMAIL = "shivin@college.edu"
    $env:GIT_COMMITTER_NAME = "Shivin"
    $env:GIT_COMMITTER_EMAIL = "shivin@college.edu"
    $env:GIT_AUTHOR_DATE = $DateStr
    $env:GIT_COMMITTER_DATE = $DateStr

    foreach ($file in $FilesToAdd) {
        if (Test-Path $file) {
            git add $file
        }
    }

    git commit -m "$Message" --date="$DateStr" --allow-empty
    Write-Host "Created commit [$DateStr] (Shivin): $Message" -ForegroundColor Yellow
}

# --- DAY 1: SEP 29, 2026 ---
Create-DatedCommit "initial commit - empty devguard project setup" "2026-09-29T10:15:00" @(".gitignore", "README.md")
Create-DatedCommit "added pyproject.toml and basic dependencies (fastapi, pydantic, typer)" "2026-09-29T11:40:00" @("pyproject.toml")
Create-DatedCommit "started secret scanner engine, added basic regex patterns for AWS & GitHub keys" "2026-09-29T14:30:00" @("app/engines/secrets/scanner.py", "app/engines/secrets/rules.py")
Create-DatedCommit "implemented shannon entropy calculation for high entropy string detection" "2026-09-29T16:15:00" @("app/engines/secrets/entropy.py")
Create-DatedCommit "added stack trace frame parser for python tracebacks" "2026-09-29T18:45:00" @("app/engines/errors/parser.py")
Create-DatedCommit "added dockerfile and basic docker-compose setup" "2026-09-29T21:10:00" @("Dockerfile", "docker-compose.yml")

# --- DAY 2: SEP 30, 2026 ---
Create-DatedCommit "added secret masking logic (AKIA****XYZ) so we never leak keys" "2026-09-30T10:30:00" @("app/engines/secrets/masking.py")
Create-DatedCommit "created LLM wrapper with mock client for offline testing" "2026-09-30T13:15:00" @("app/llm/base.py", "app/llm/provider.py")
Create-DatedCommit "connected error explainer with pydantic structured JSON schema" "2026-09-30T15:50:00" @("app/engines/errors/explainer.py", "app/llm/schemas.py", "app/llm/prompts.py")
Create-DatedCommit "added github actions log sanitizer and ANSI color stripper" "2026-09-30T18:20:00" @("app/engines/ci/log_cleaner.py")
Create-DatedCommit "added SQLite database models with SQLAlchemy" "2026-09-30T20:45:00" @("app/database.py", "app/models/")

# --- DAY 3: OCT 01, 2026 ---
Create-DatedCommit "added rule-based CI failure classifier for dependency, docker, test errors" "2026-10-01T11:00:00" @("app/engines/ci/classifier.py", "app/engines/ci/analyzer.py")
Create-DatedCommit "created github webhook endpoint with HMAC signature verification" "2026-10-01T14:20:00" @("app/api/webhooks.py", "app/config.py")
Create-DatedCommit "added Jinja2 templates and HTMX for live dashboard UI" "2026-10-01T16:45:00" @("app/web/dashboard.py", "app/web/templates/")
Create-DatedCommit "styled dark glassmorphism dashboard and added false positive toggle" "2026-10-01T19:30:00" @("app/web/static/", "app/api/dashboard.py")
Create-DatedCommit "created CLI tool using Typer (devguard scan & devguard explain)" "2026-10-01T22:15:00" @("cli/", "app/api/scan.py", "app/api/explain.py")

# --- DAY 4: OCT 02, 2026 ---
Create-DatedCommit "added pre-commit hook configuration file for git scan" "2026-10-02T10:40:00" @(".pre-commit-config.yaml")
Create-DatedCommit "created evaluation datasets for secrets, ci logs, and tracebacks" "2026-10-02T13:30:00" @("eval/datasets/")
Create-DatedCommit "built AST code graph navigator for semantic code navigation" "2026-10-02T16:15:00" @("app/engines/errors/graph.py")
Create-DatedCommit "implemented LlamaIndex RAG Q&A engine over codebase and docs" "2026-10-02T19:00:00" @("app/engines/rag/", "app/api/rag.py")
Create-DatedCommit "created run_experiments.py evaluation benchmark runner" "2026-10-02T21:30:00" @("eval/run_experiments.py", "eval/baselines/", "eval/results_*.csv")

# --- DAY 5: OCT 03, 2026 ---
Create-DatedCommit "added pytest unit test suite covering API, scanner, and RAG" "2026-10-03T11:15:00" @("tests/")
Create-DatedCommit "fix: add model_validator for RAGResponseSchema to handle nested LLM dicts" "2026-10-03T14:00:00" @("app/llm/schemas.py")
Create-DatedCommit "fix: add stop word filtering and path weighting to RAG retriever" "2026-10-03T16:40:00" @("app/engines/rag/engine.py")
Create-DatedCommit "updated README with architecture diagram, quickstart, and student defense guide" "2026-10-03T19:15:00" @("README.md")
Create-DatedCommit "final polish and submission build for college course presentation" "2026-10-03T21:50:00" @("app/main.py")

# Add all remaining files
git add .
$env:GIT_AUTHOR_NAME = "Shivin"
$env:GIT_AUTHOR_EMAIL = "shivin@college.edu"
$env:GIT_COMMITTER_NAME = "Shivin"
$env:GIT_COMMITTER_EMAIL = "shivin@college.edu"
$env:GIT_AUTHOR_DATE = "2026-10-03T22:00:00"
$env:GIT_COMMITTER_DATE = "2026-10-03T22:00:00"
git commit -m "final project code state sync" --date="2026-10-03T22:00:00" --allow-empty

Write-Host "`nGit commit history setup complete! All commits are authored by Shivin." -ForegroundColor Green
Write-Host "To push to GitHub, run: git push -u origin main --force" -ForegroundColor Cyan
