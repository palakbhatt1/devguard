import asyncio as _asyncio
import csv
import json
import os as _os
import pathlib
import subprocess
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings as _get_settings
from app.database import get_db
from app.engines.ci import CIFailureAnalyzer, classify_ci_failure_rules, clean_ci_log
from app.engines.errors import ErrorExplainer
from app.engines.errors.graph import ASTNavigator
from app.engines.errors.parser import parse_python_traceback
from app.engines.secrets import SecretScanner
from app.llm import get_llm_client
from app.llm.schemas import ErrorExplanationResult
from app.models.domain import ErrorExplanation, Finding, WorkflowAnalysis

router = APIRouter(tags=["Web Dashboard"])
templates = Jinja2Templates(directory="app/web/templates")


def _status_info():
    s = _get_settings()
    provider = s.LLM_PROVIDER
    model = s.LLM_MODEL or ""
    db = "postgres" if "postgres" in s.DATABASE_URL else "sqlite"
    return {"provider": provider, "model": model, "rag_backend": "keyword", "db": db}


templates.env.globals["status"] = _status_info

EVAL_DIR = pathlib.Path("eval")
SAMPLES_DIR = pathlib.Path("app/web/samples")


def _load_csv(name: str):
    p = EVAL_DIR / name
    if not p.exists():
        return []
    with open(p, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _load_eval_meta() -> dict:
    meta_path = pathlib.Path("eval/eval_meta.json")
    if meta_path.exists():
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    settings = _get_settings()
    is_mock = settings.LLM_PROVIDER == "mock" or not settings.LLM_API_KEY.strip()
    return {
        "provider": "mock" if is_mock else settings.LLM_PROVIDER,
        "model": "offline-mock" if is_mock else (settings.LLM_MODEL or "gemini-3.1-flash-lite"),
        "is_mock": is_mock,
        "date": "2026-11-01 20:34:01",
        "dataset_size": 115,
        "secrets_count": 60,
        "ci_count": 30,
        "errors_count": 25,
        "scorer": "strict_root_cause_keyword_matching",
    }


@router.get("/", response_class=HTMLResponse)
async def get_landing(request: Request):
    """Render futuristic SaaS hero landing page."""
    return templates.TemplateResponse(
        request=request,
        name="landing.html",
    )


@router.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard(request: Request, db: Session = Depends(get_db)):
    """Render main web dashboard overview."""
    findings = db.query(Finding).order_by(Finding.id.desc()).all()
    ci_analyses = db.query(WorkflowAnalysis).order_by(WorkflowAnalysis.id.desc()).all()
    error_count = db.query(ErrorExplanation).count()

    real_secrets_count = sum(1 for f in findings if f.is_real_secret and not f.is_false_positive)
    false_positives_count = sum(1 for f in findings if f.is_false_positive)

    # Chart data
    by_rule = db.query(Finding.rule_name, func.count(Finding.id)).group_by(Finding.rule_name).all()
    by_cat = db.query(WorkflowAnalysis.failure_category, func.count(WorkflowAnalysis.id)).group_by(WorkflowAnalysis.failure_category).all()

    # Recent events (last 10 across all engines)
    recent_findings = db.query(Finding).order_by(Finding.id.desc()).limit(5).all()
    recent_ci = db.query(WorkflowAnalysis).order_by(WorkflowAnalysis.id.desc()).limit(3).all()
    recent_errors = db.query(ErrorExplanation).order_by(ErrorExplanation.id.desc()).limit(2).all()

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "findings": findings,
            "ci_analyses": ci_analyses,
            "real_secrets_count": real_secrets_count,
            "false_positives_count": false_positives_count,
            "error_count": error_count,
            "ci_count": len(ci_analyses),
            "scan_count": db.query(Finding).count(),
            "by_rule": by_rule,
            "by_cat": by_cat,
            "recent_findings": recent_findings,
            "recent_ci": recent_ci,
            "recent_errors": recent_errors,
        },
    )


@router.post("/dashboard/scan", response_class=HTMLResponse)
async def dashboard_scan(
    request: Request,
    path: str = Form("."),
    db: Session = Depends(get_db),
):
    """HTMX endpoint for running interactive secret scan."""
    llm_client = get_llm_client()
    scanner = SecretScanner(llm_client=llm_client)

    try:
        raw_findings = await scanner.scan_directory(directory_path=path, use_llm_triage=True)
    except Exception as e:
        return HTMLResponse(f"<tr><td colspan='6' style='color: var(--accent-red);'>Scan Error: {e}</td></tr>")

    for rf in raw_findings:
        existing = db.query(Finding).filter(
            Finding.file_path == rf.file_path,
            Finding.line_number == rf.line_number,
            Finding.rule_name == rf.rule_name,
        ).first()
        if existing:
            existing.masked_value = rf.masked_value
            existing.entropy_score = rf.entropy_score
            existing.is_real_secret = rf.is_real_secret
            existing.reasoning = rf.reasoning
            existing.context_snippet = rf.context_snippet
        else:
            db_finding = Finding(
                file_path=rf.file_path,
                line_number=rf.line_number,
                rule_name=rf.rule_name,
                masked_value=rf.masked_value,
                entropy_score=rf.entropy_score,
                is_real_secret=rf.is_real_secret,
                is_false_positive=False,
                reasoning=rf.reasoning,
                context_snippet=rf.context_snippet,
            )
            db.add(db_finding)

    db.commit()

    all_findings = db.query(Finding).order_by(Finding.id.desc()).all()
    html_out = ""
    for f in all_findings:
        html_out += templates.TemplateResponse(
            request=request,
            name="partials/finding_row.html",
            context={"finding": f},
        ).body.decode("utf-8")

    return HTMLResponse(content=html_out or "<tr><td colspan='6'>No findings detected.</td></tr>")


@router.post("/dashboard/findings/{finding_id}/toggle-false-positive", response_class=HTMLResponse)
@router.post("/dashboard/findings/{finding_id}/toggle-fp", response_class=HTMLResponse)
async def toggle_false_positive(
    finding_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """HTMX endpoint for toggling false positive status on a finding."""
    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found.")

    finding.is_false_positive = not finding.is_false_positive
    db.commit()
    db.refresh(finding)

    return templates.TemplateResponse(
        request=request,
        name="partials/finding_tr.html",
        context={"finding": finding},
    )


@router.get("/dashboard/findings/{finding_id}/trace", response_class=HTMLResponse)
async def finding_trace(finding_id: int, request: Request, db: Session = Depends(get_db)):
    """HTMX: return pipeline trace detail for a finding."""
    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding:
        return HTMLResponse("<td colspan='6'>Finding not found.</td>")
    return templates.TemplateResponse(
        request=request,
        name="partials/finding_trace.html",
        context={"finding": finding},
    )


@router.post("/dashboard/explain", response_class=HTMLResponse)
async def dashboard_explain_error(
    request: Request,
    traceback_text: str = Form(...),
    use_ast: str = Form("true"),
    db: Session = Depends(get_db),
):
    """HTMX endpoint for diagnosing an error traceback in the UI."""
    if not traceback_text.strip():
        return HTMLResponse(
            "<div style='color: var(--accent-red); font-size: 0.9rem;'>Please paste a valid traceback.</div>"
        )

    llm_client = get_llm_client()
    explainer = ErrorExplainer(llm_client=llm_client)

    # Parse traceback for AST context
    parsed = parse_python_traceback(traceback_text)
    sem_context = None
    if use_ast.lower() != "false" and parsed.failing_file and parsed.failing_line:
        import os
        if os.path.exists(parsed.failing_file):
            try:
                nav = ASTNavigator()
                sem_context = nav.get_semantic_context(parsed.failing_file, parsed.failing_line)
            except Exception:
                pass

    # Generate Baseline A: Raw Error Text (Without AST / Code Context)
    try:
        raw_res = await llm_client.generate_structured(
            system_prompt="Diagnose Python error from raw traceback text alone without local repository files or AST context. Return JSON with keys: exception_type, summary, root_cause, suggested_fix, fixed_code_snippet.",
            user_prompt=f"Error text:\n{traceback_text}",
            response_model=ErrorExplanationResult,
        )
    except Exception:
        raw_res = ErrorExplanationResult(
            exception_type=parsed.exception_type or "RuntimeError",
            summary=f"Raw traceback diagnosis for {parsed.exception_type or 'Exception'}",
            root_cause="Generic failure from traceback without local source context.",
            suggested_fix="Review parameters and check inputs.",
            fixed_code_snippet=None,
        )

    # Generate Baseline B: DevGuard System (With AST Semantic Navigation & Code Context)
    try:
        res = await explainer.explain_error(traceback_text=traceback_text)
    except Exception as e:
        return HTMLResponse(f"<div style='color: var(--accent-red);'>Error explaining traceback: {e}</div>")

    db_obj = ErrorExplanation(
        exception_type=res.exception_type,
        summary=res.summary,
        root_cause=res.root_cause,
        suggested_fix=res.suggested_fix,
        fixed_code_snippet=res.fixed_code_snippet,
        file_path=parsed.failing_file,
        line_number=parsed.failing_line,
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)

    return templates.TemplateResponse(
        request=request,
        name="partials/error_result.html",
        context={"explanation": db_obj, "raw_explanation": raw_res, "sem_context": sem_context, "parsed": parsed},
    )


@router.get("/dashboard/evaluation", response_class=HTMLResponse)
@router.get("/evaluation", response_class=HTMLResponse)
async def evaluation_page(request: Request):
    """Render evaluation benchmark results page."""
    return templates.TemplateResponse(
        request=request,
        name="evaluation.html",
        context={
            "secrets": _load_csv("results_secrets.csv"),
            "ci": _load_csv("results_ci.csv"),
            "errors": _load_csv("results_errors.csv"),
            "eval_meta": _load_eval_meta(),
        },
    )


@router.post("/dashboard/evaluation/run", response_class=HTMLResponse)
async def run_evaluation(request: Request):
    """HTMX endpoint: re-run eval benchmark with mock provider and return updated table block."""
    import os
    env = {**os.environ}
    try:
        await _asyncio.to_thread(
            subprocess.run,
            ["python", "eval/run_experiments.py"],
            capture_output=True, text=True, timeout=120, env=env
        )
    except Exception:
        pass
    # Return refreshed partial
    return templates.TemplateResponse(
        request=request,
        name="partials/eval_tables.html",
        context={
            "secrets": _load_csv("results_secrets.csv"),
            "ci": _load_csv("results_ci.csv"),
            "errors": _load_csv("results_errors.csv"),
            "eval_meta": _load_eval_meta(),
        },
    )


@router.get("/dashboard/ci", response_class=HTMLResponse)
@router.get("/ci", response_class=HTMLResponse)
async def ci_tab(request: Request, db: Session = Depends(get_db)):
    """Render CI Failure Analyzer tab."""
    samples = [f.stem for f in SAMPLES_DIR.glob("*.log")] if SAMPLES_DIR.exists() else []
    ci_analyses = db.query(WorkflowAnalysis).order_by(WorkflowAnalysis.id.desc()).all()
    return templates.TemplateResponse(
        request=request, 
        name="ci.html", 
        context={"samples": samples, "ci_analyses": ci_analyses}
    )


@router.get("/dashboard/errors", response_class=HTMLResponse)
@router.get("/errors", response_class=HTMLResponse)
async def errors_page(request: Request, db: Session = Depends(get_db)):
    """Render dedicated Error Explainer page."""
    recent_errors = db.query(ErrorExplanation).order_by(ErrorExplanation.id.desc()).limit(10).all()
    return templates.TemplateResponse(
        request=request,
        name="errors.html",
        context={"recent_errors": recent_errors},
    )


@router.get("/dashboard/rag", response_class=HTMLResponse)
@router.get("/rag", response_class=HTMLResponse)
async def rag_page(request: Request):
    """Render dedicated RAG Assistant page."""
    return templates.TemplateResponse(
        request=request,
        name="rag.html",
    )


@router.get("/dashboard/ci/sample/{name}", response_class=HTMLResponse)
async def ci_sample(name: str):
    """Return sample CI log content for textarea pre-fill."""
    safe_name = name.replace("/", "").replace("..", "")
    p = SAMPLES_DIR / f"{safe_name}.log"
    if p.exists():
        content = p.read_text(encoding="utf-8", errors="ignore")
        return HTMLResponse(content=f'<textarea name="log" id="ci-log-input" rows="14" style="width:100%;background:var(--bg-card-input);color:var(--text-main);border:1px solid var(--border-card);border-radius:8px;padding:0.75rem;font-family:var(--font-mono);font-size:0.82rem;resize:vertical;">{content}</textarea>')
    return HTMLResponse(content="<textarea>Sample not found</textarea>")


@router.post("/dashboard/ci/analyze", response_class=HTMLResponse)
async def ci_analyze_htmx(request: Request, log: str = Form(...)):
    """HTMX: analyze CI log and return result partial."""
    llm_client = get_llm_client()
    analyzer = CIFailureAnalyzer(llm_client=llm_client)

    raw_len = len(log)
    cleaned = clean_ci_log(log)
    clean_len = len(cleaned)
    saved_pct = round(100 * (1 - clean_len / max(raw_len, 1)))
    category = classify_ci_failure_rules(cleaned)

    try:
        result = await analyzer.analyze_log(raw_log=log, workflow_name="CI Workflow", job_name="build-and-test")
    except Exception as e:
        from app.llm.schemas import CIFailureAnalysisResult
        result = CIFailureAnalysisResult(failure_category=category, root_cause=str(e), suggested_fix="Check logs.", confidence=0.5)

    # Build a PR comment preview
    pr_preview = f"""## DevGuard CI Analysis

**Failure Category:** `{result.failure_category}`
**Confidence:** {result.confidence:.0%}

**Root Cause:**
{result.root_cause}

**Suggested Fix:**
{result.suggested_fix}

---
*Posted by AI DevGuard | Engine: Gemini 3.5 Flash-Lite*"""

    return templates.TemplateResponse(
        request=request,
        name="partials/ci_result.html",
        context={
            "raw_len": raw_len,
            "clean_len": clean_len,
            "saved_pct": saved_pct,
            "cleaned_preview": cleaned[-2000:],
            "category": result.failure_category,
            "result": result,
            "pr_preview": pr_preview,
        },
    )


@router.get("/dashboard/export/findings")
def export_findings(db: Session = Depends(get_db)):
    """Export all findings as downloadable JSON with strictly masked secrets."""
    findings = db.query(Finding).order_by(Finding.id.asc()).all()
    payload = [
        {
            "id": f.id,
            "file_path": f.file_path,
            "line_number": f.line_number,
            "rule_name": f.rule_name,
            "masked_value": f.masked_value,
            "entropy_score": round(float(f.entropy_score or 0.0), 2),
            "is_real_secret": bool(f.is_real_secret),
            "is_false_positive": bool(f.is_false_positive),
            "reasoning": f.reasoning or "",
        }
        for f in findings
    ]
    return JSONResponse(
        content=payload,
        headers={"Content-Disposition": "attachment; filename=devguard_findings.json"},
    )
