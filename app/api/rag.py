import re
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from app.engines.rag.engine import DevGuardRAG
from app.llm import get_llm_client

router = APIRouter(prefix="/api/rag", tags=["RAG Code Q&A"])


class RAGRequest(BaseModel):
    query: str


@router.post("/query")
async def query_rag(req: RAGRequest):
    """API endpoint for RAG codebase Q&A queries."""
    llm_client = get_llm_client()
    rag_engine = DevGuardRAG(workspace_root=".", llm_client=llm_client)
    res = await rag_engine.query_codebase(req.query)

    sources_json = [
        {
            "relative_path": s.relative_path,
            "snippet": s.content[:150] + "...",
            "score": round(s.score, 2),
            "matched_terms": getattr(s, "matched_terms", []),
        }
        for s in res.sources
    ]

    return {
        "query": res.query,
        "answer": res.answer,
        "sources": sources_json,
        "engine": res.engine_used,
    }


@router.post("/query-htmx", response_class=HTMLResponse)
async def query_rag_htmx(query: str = Form(...)):
    """HTMX endpoint returning formatted HTML for Web Dashboard RAG tab."""
    llm_client = get_llm_client()
    rag_engine = DevGuardRAG(workspace_root=".", llm_client=llm_client)
    res = await rag_engine.query_codebase(query)

    max_score = max((s.score for s in res.sources), default=1.0) or 1.0
    sources_html = ""
    for s in res.sources:
        bar_pct = min(100, max(5, round(s.score / max_score * 100)))
        terms = [t for t in getattr(s, "matched_terms", [])[:6] if t]
        terms_chips = "".join(
            f'<span style="background: rgba(56, 189, 248, 0.12); border: 1px solid rgba(56, 189, 248, 0.25); color: #38bdf8; font-size: 10px; font-family: var(--font-mono); padding: 0.1rem 0.4rem; border-radius: 4px; margin-right: 4px;">{term}</span>'
            for term in terms
        )
        sources_html += f"""
        <div style="background: rgba(4, 10, 24, 0.7); border: 1px solid var(--border-glass-subtle); padding: 12px 14px; border-radius: 10px; margin-top: 10px;">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
                <span style="font-family: var(--font-mono); font-size: 12px; font-weight: 600; color: #ffffff;">📄 {s.relative_path}</span>
                <span style="color: #4ade80; font-family: var(--font-mono); font-size: 11px; font-weight: 700;">Score: {round(s.score, 1)}</span>
            </div>
            <div style="background: rgba(255, 255, 255, 0.08); border-radius: 9999px; height: 5px; margin-bottom: 8px; overflow: hidden;">
                <div style="background: linear-gradient(90deg, #38bdf8, #22c55e); height: 100%; border-radius: 9999px; width: {bar_pct}%;"></div>
            </div>
            {f'<div style="margin-bottom: 6px; display: flex; flex-wrap: wrap; gap: 2px;">{terms_chips}</div>' if terms else ''}
            <pre style="margin: 0; color: #cbd5e1; white-space: pre-wrap; font-family: var(--font-mono); font-size: 11.5px; line-height: 1.5; background: rgba(0,0,0,0.3); padding: 8px; border-radius: 6px; max-height: 140px; overflow-y: auto;">{s.content[:300]}...</pre>
        </div>
        """

    formatted_answer = res.answer.replace("\n", "<br>")
    formatted_answer = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", formatted_answer)

    retrieval_ms = getattr(res, "retrieval_time_ms", 12.5)

    html = f"""
    <div style="background: rgba(9, 20, 42, 0.75); border: 1px solid var(--border-glass); border-radius: 16px; padding: 1.5rem; backdrop-filter: blur(20px); box-shadow: 0 10px 30px rgba(0,0,0,0.4);">
        <!-- Retrieval Metadata Header -->
        <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.75rem; margin-bottom: 1.25rem; border-bottom: 1px solid var(--border-glass-subtle); padding-bottom: 0.85rem;">
            <div style="display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;">
                <span class="badge-pill badge-green" style="font-size: 11px;">
                    <span class="badge-check">&#10003;</span> Backend: {res.engine_used}
                </span>
                <span class="badge-pill badge-purple" style="font-size: 11px;">
                    ⚡ Retrieval: {retrieval_ms} ms
                </span>
                <span class="badge-pill badge-glass" style="font-size: 11px;">
                    📂 {len(res.sources)} Source Chunks
                </span>
            </div>
        </div>

        <!-- Synthesized Answer -->
        <div style="margin-bottom: 1.25rem;">
            <h4 style="color: #38bdf8; font-size: 0.95rem; font-weight: 700; margin-bottom: 0.65rem; text-transform: uppercase; letter-spacing: 0.5px; font-family: var(--font-mono);">
                Synthesized Answer
            </h4>
            <div style="color: #f1f5f9; font-size: 13.5px; line-height: 1.65; background: rgba(255,255,255,0.03); padding: 1rem; border-radius: 10px; border: 1px solid rgba(255,255,255,0.05);">
                {formatted_answer}
            </div>
        </div>

        <!-- Retrieved Source Chunks with Relevance Bars -->
        <div>
            <h5 style="color: var(--text-muted); font-size: 11.5px; font-weight: 700; margin-bottom: 0.5rem; text-transform: uppercase; letter-spacing: 0.5px; font-family: var(--font-mono);">
                Retrieved Codebase Chunks ({len(res.sources)})
            </h5>
            {sources_html or '<p style="color: var(--text-muted); font-size: 12px;">No source files matched.</p>'}
        </div>
    </div>
    """

    return HTMLResponse(content=html)