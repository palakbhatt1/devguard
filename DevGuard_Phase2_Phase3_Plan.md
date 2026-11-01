# AI DevGuard: Phase 2 and Phase 3 Plan

Phase 2 = what you build now, for tomorrow's evaluation. Dashboard first, terminal second.
Phase 3 = what completes the project afterwards.

Snippets are sketches. I have not seen your source, only paths and function names from your docs (`app/api/dashboard.py`, `app/web/templates/`, `cli/main.py`, `app/engines/...`). Adapt names to your repo.

Rule for everything shown: label the provider on screen. If the Mock LLM produced a number, the UI must say "mock". Never present mock results as real.

---

## Where things stand (issues and what fixes them)

| Issue | Fix | When |
|---|---|---|
| Evaluation data is synthetic (self-generated) | Run on real public datasets (see E1) | Parked: Phase 3 |
| Error-explainer shows 0% correct-cause | Debug the scorer or mock output, re-run with a real LLM | Phase 2, first |
| Results may come from the Mock LLM | Real-LLM runs, provider badge on every page | Phase 2 |
| Secret recall 70% (goal 80%), precision below baseline | Error analysis, new rules, per-rule entropy thresholds | Phase 3 (P3-2) |
| RAG label says LlamaIndex / LangChain but it is custom keyword search | Fix label now, add embedding backend later | Label in Phase 2, backend in Phase 3 |
| Dashboard shows outputs but not the pipeline | Seven dashboard features D1 to D8 | Phase 2 |
| CLI has only `scan` and `explain` | `status`, `ask`, `ci analyze`, `eval` now; `hook install`, `demo`, SARIF later | Phase 2 and Phase 3 |
| No CI workflow in own repo, not deployed | `ci.yml`, Docker, Render/Railway | Phase 3 |

---

# PHASE 2

## What the dashboard has now vs what we add

Now: scan workspace, false-positive toggle, error explainer tab, Ask DevGuard AI tab.
Problem: it shows outputs but not the system's intelligence, so the terminal ends up carrying the demo.

Phase 2 adds seven dashboard features. Each one shows something your pipeline does that a plain scanner or ChatGPT does not.

---

## D1. Header status badge (15 min)

**What:** a badge in the top bar: `LLM: gemini (gemini-3.1-flash-lite) | RAG: keyword | DB: sqlite`. Turns amber and reads `LLM: mock` when mock is active.

**Why:** honesty, and it answers "is this real?" before anyone asks.

**How**
- `app/api/dashboard.py`: pass `status` into every template context (or a Jinja global).
  ```python
  def get_status():
      return {"provider": settings.llm_provider, "model": getattr(settings, "llm_model", ""),
              "rag_backend": getattr(settings, "rag_backend", "keyword"),
              "db": "postgres" if "postgres" in settings.database_url else "sqlite"}
  templates.env.globals["status"] = get_status
  ```
- `app/web/templates/base.html`, inside the header:
  ```html
  <span class="badge {{ 'badge-warn' if status().provider == 'mock' else 'badge-ok' }}">
    LLM: {{ status().provider }} {{ status().model }} | RAG: {{ status().rag_backend }} | DB: {{ status().db }}
  </span>
  ```
- Add `.badge`, `.badge-ok`, `.badge-warn` to your existing CSS variables.

---

## D2. Overview page with stat cards and charts (1 hr)

**What:** a landing page at `/dashboard` showing:
- Cards: total scans, secrets found, false positives marked, CI analyses, errors explained, RAG questions asked.
- Chart 1: findings by secret type (AWS, GitHub, Slack, Stripe, generic).
- Chart 2: CI failures by category (test_failure, dependency_conflict, lint_error, docker_build, missing_secret, timeout).
- Table: last 10 events across all engines.

**How**
- Add one query function per number in `app/api/dashboard.py` using your SQLAlchemy models (check names in `app/models/`):
  ```python
  @router.get("/dashboard")
  def overview(request: Request, db: Session = Depends(get_db)):
      stats = {
          "scans": db.query(ScanRun).count(),
          "secrets": db.query(Finding).count(),
          "false_pos": db.query(Finding).filter(Finding.is_false_positive.is_(True)).count(),
          "ci": db.query(CIAnalysis).count(),
      }
      by_type = db.query(Finding.rule_name, func.count()).group_by(Finding.rule_name).all()
      by_cat = db.query(CIAnalysis.category, func.count()).group_by(CIAnalysis.category).all()
      return templates.TemplateResponse("overview.html", {"request": request, "stats": stats,
          "by_type": by_type, "by_cat": by_cat})
  ```
- New template `app/web/templates/overview.html` extending `base.html`. Render cards in a CSS grid. Draw charts with Chart.js from a CDN (the dashboard runs locally, so a CDN script is fine):
  ```html
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1"></script>
  <canvas id="byType"></canvas>
  <script>
    new Chart(document.getElementById('byType'), {
      type: 'bar',
      data: { labels: {{ by_type|map(attribute=0)|list|tojson }},
              datasets: [{ data: {{ by_type|map(attribute=1)|list|tojson }} }] }
    });
  </script>
  ```
- If you have no history in the DB yet, run `devguard scan .`, a few CI logs and tracebacks first so the page is not empty. Seed script: `scripts/seed_demo_data.py` (see D8).

---

## D3. Evaluation Results page (1 hr) - highest value

**What:** `/dashboard/evaluation` shows your benchmark as tables and bar charts, read from `eval/results_*.csv`:
- Secrets: precision, recall, F1, false alarm rate for Rules Only, detect-secrets, DevGuard.
- CI: accuracy for Rule Classifier, Raw Log + LLM, DevGuard (56.67 / 40.00 / 90.00).
- Errors: raw error text vs AST-resolved context.
- Metadata line: provider, model, run date, dataset size.
- A "Run benchmark" HTMX button that re-runs it on the mock provider and refreshes the page.

**Why:** this is your research result, and it needs no live LLM call, so it cannot fail in front of an evaluator.

**How**
- Route:
  ```python
  import csv, pathlib
  EVAL = pathlib.Path("eval")

  def load(name):
      p = EVAL / name
      return list(csv.DictReader(p.open())) if p.exists() else []

  @router.get("/dashboard/evaluation")
  def evaluation(request: Request):
      return templates.TemplateResponse("evaluation.html", {"request": request,
          "secrets": load("results_secrets.csv"),
          "ci": load("results_ci.csv"),
          "errors": load("results_errors.csv")})
  ```
- Template: loop rows into a table, and feed the same data to a Chart.js grouped bar chart. Highlight the DevGuard row.
- Button:
  ```html
  <button hx-post="/dashboard/evaluation/run" hx-target="#eval-body" hx-swap="outerHTML"
          hx-indicator="#spin">Run benchmark (mock)</button>
  ```
  The POST route runs `python eval/run_experiments.py` with `LLM_PROVIDER=mock` via `subprocess.run` (use `asyncio.to_thread` so it does not block) and returns the refreshed block.
- Do this first: re-run the benchmark with a real provider tonight and save `results_*_real.csv`. Show the real file by default and the mock file behind a toggle. Fix the error-explainer 0% (compare `expected` vs `predicted` in `eval/run_experiments.py`; the scorer is probably doing exact string matching or the mock returns a fixed string).

---

## D4. CI Failure Analyzer tab (1 hr)

**What:** a new tab: paste a build log (or pick a sample from a dropdown), click Analyze. The page shows:
- Raw size vs cleaned size and percent saved.
- A cleaned-log preview with the failing lines highlighted.
- Category badge from the rule classifier (for example `dependency_conflict`).
- LLM result: root cause and suggested fix.
- A "Posted as PR comment" preview, rendered exactly as the GitHub markdown would look.

**Why:** shows cleaning, classification and the LLM as separate visible stages. This is your 90% result, live.

**How**
- Route:
  ```python
  @router.post("/dashboard/ci/analyze", response_class=HTMLResponse)
  async def ci_analyze(request: Request, log: str = Form(...)):
      cleaned = clean_log(log)                       # app/engines/ci/log_cleaner.py
      category = classify(cleaned)                   # app/engines/ci/classifier.py
      result = await analyze_ci(cleaned, category)   # real engine entry point
      return templates.TemplateResponse("partials/ci_result.html", {"request": request,
          "raw_len": len(log), "clean_len": len(cleaned), "saved": round(100*(1-len(cleaned)/max(len(log),1))),
          "cleaned": cleaned[-3000:], "category": category, "result": result})
  ```
- Form (in a new `ci.html`):
  ```html
  <form hx-post="/dashboard/ci/analyze" hx-target="#ci-out" hx-indicator="#spin">
    <textarea name="log" rows="12"></textarea>
    <button>Analyze</button>
  </form>
  <div id="ci-out"></div>
  ```
- Sample dropdown: put 4 sample logs in `app/web/samples/` (test failure, dependency conflict, lint error, docker build) and fill the textarea with a small `hx-get`.
- Reuse `app/github/pr_comment.py`'s formatter to render the PR comment preview.

---

## D5. Secret findings with pipeline trace (1 hr)

**What:** in the findings table, each row expands (HTMX `hx-get` into a detail row) to show that finding's journey:
1. Regex rule that matched (for example `aws_access_key`).
2. Shannon entropy score and the threshold used.
3. Masked value (`AKIA****CDEF`), with a note that this is what the LLM saw.
4. The context lines sent to the LLM.
5. LLM verdict, confidence and reason (real secret vs placeholder).
Plus a verdict badge in the main table and a filter: All / Real / Likely placeholder / Marked false positive.

**How**
- Store the intermediate values at scan time. In `scanner.py`, when you build a finding, keep `entropy`, `rule_name`, `masked`, `context` and the triage result. Add the columns to the Finding model (and an Alembic migration, or recreate the SQLite DB for the demo).
- Route `GET /dashboard/findings/{id}/trace` returning `partials/trace.html`.
- Row:
  ```html
  <tr hx-get="/dashboard/findings/{{ f.id }}/trace" hx-target="#trace-{{ f.id }}" hx-trigger="click">...</tr>
  <tr><td colspan="6" id="trace-{{ f.id }}"></td></tr>
  ```
- Never render a cleartext secret anywhere in the UI.

---

## D6. Error Explainer with AST context panel (1 hr)

**What:** next to the LLM diagnosis, show what the AST navigator found:
- Enclosing class and function of the failing line.
- Functions called near that line.
- Imported symbols resolved to other files, with a collapsible code snippet for each (file path and line range).
- A toggle "Explain without AST context" that re-runs with the raw traceback only, side by side.

**Why:** AST navigation is your most distinctive feature and it is invisible right now.

**How**
- In `app/engines/errors/explainer.py` make sure the result object includes the `SemanticCodeContext` (scope, called functions, resolved imports). Add it to the response model if it is only used internally.
- Template `partials/error_result.html` with two columns: left "Context DevGuard built" (scope, calls, imports as `<details>` blocks with `<pre>`), right "Diagnosis" (summary, root cause, fix, confidence).
- Toggle: a second `hx-post` to the same route with `use_ast=false`, rendered in a second column for comparison.

---

## D7. Ask DevGuard with retrieval transparency (45 min)

**What:** after each answer show a "Retrieval" panel: top chunks as cards with file path, score bar, and the matched keywords highlighted. Also show the backend name (`Keyword RAG`) and retrieval latency.

**Why:** makes RAG explainable and sets up the embeddings comparison in Phase 3.

**How**
- The `/api/rag/query` response already has `sources` with `score`. Add `snippet` and `matched_terms` in `engine.py` `retrieve()`.
- Template: score bar as `<div class="bar" style="width: {{ (s.score / max_score * 100)|round }}%">`.
- Fix the label now: set `engine_used` to `"Keyword RAG"` and change the docstring so the UI does not claim LlamaIndex or LangChain.

---

## D8. Demo data seeder (30 min)

**What:** `scripts/seed_demo_data.py` that fills the DB with realistic history: a few scans with planted fake secrets, 4 to 6 CI analyses across categories, a couple of explained tracebacks, a few RAG questions.

**How:** call your own engines directly (mock provider is fine), so the Overview charts and tables are populated for the demo. Run it once before the evaluation.

---

## E1. Real-data evaluation (parked: moved to Phase 3, P3-1)

**Why:** your own datasets are synthetic, so the failures may be easier than real ones. Real public datasets fix that.

| Engine | Dataset | What it is | Label you evaluate against |
|---|---|---|---|
| Secrets | SecretBench (Basak et al., MSR 2023) | 97,479 candidate secrets from 818 GitHub repos, 15,084 manually labeled true | true secret vs false positive |
| CI logs | LogChunks (Brandt et al., MSR 2020), Zenodo record 3632351 | 797 real Travis CI failure logs, 80 repos, 29 languages | the log chunk that explains the failure |
| Errors | BugsInPy (493 reproducible Python bugs with fixes and failing tests) and PyTraceBugs (real tracebacks from GitHub issues, MIT, on Hugging Face) | real bugs and tracebacks | the actual fix or root cause |

Caveats to state when reporting: LogChunks is Travis CI, not GitHub Actions, and has no category labels. SecretBench lives in Google BigQuery / Cloud Storage, so check what access you need before relying on it.

**Run on all of them? Yes, but not every sample through the LLM.** Rules and entropy are free and fast, so run those baselines on the full or a large dataset. LLM calls cost time, money and hit rate limits, so run them on a fixed random sample (set a seed, record it).

| Engine | Rules-only baseline | LLM systems |
|---|---|---|
| Secrets | full set, or at least 5,000 candidates | 300 samples, stratified to keep true and false in realistic proportion |
| CI logs | all 797 | 150 logs (truncate to the last 3,000 lines before cleaning) |
| Errors | all you convert | 50 to 100 tracebacks |

Rough time: one LLM call is 2 to 5 seconds. 150 logs by 2 LLM systems is about 300 calls, roughly 10 to 25 minutes sequentially, less with 4 to 5 concurrent requests. Cache every response to disk (key = hash of provider, model, prompt) so a re-run costs nothing. Do a 20-sample dry run first to catch scorer bugs before the big run.

**Metrics**
- Secrets: precision, recall, F1, false alarm rate, per system.
- CI: failure-chunk hit rate (did the root cause point at the labeled chunk), and category accuracy on a 30-log subset you label by hand.
- Errors: correct-cause rate using exception type plus keywords, or an LLM-as-judge with a strict yes/no schema.

**How**
1. Download into `eval/datasets/real/` (do not commit large files; add the folder to `.gitignore` and keep a `README.md` with sources and licences).
2. Write converters that output your existing CSV schema plus `source` and `label`:
   ```python
   # scripts/convert_logchunks.py (sketch; inspect the unzipped layout first)
   import csv, random, pathlib
   random.seed(42)
   rows = []
   for log in pathlib.Path("eval/datasets/real/LogChunks/logs").rglob("*.log"):
       rows.append({"log": log.read_text(errors="ignore")[-60000:], "source": "logchunks", "path": str(log)})
   sample = random.sample(rows, 150)
   with open("eval/datasets/ci_real.csv", "w", newline="") as f:
       w = csv.DictWriter(f, fieldnames=["log", "source", "path"]); w.writeheader(); w.writerows(sample)
   ```
   Join the failure-chunk labels from each repo's `build-failure-reason` XML onto these rows.
3. Secrets converter: export a labeled sample from SecretBench to `eval/datasets/secrets_real.csv` with columns `text,label,source` (keep the surrounding code lines as context).
4. Add `--dataset synthetic|real` to `eval/run_experiments.py`, write `results_*_real.csv`, and show both sets side by side on the Evaluation page.
5. Do not paste real secrets from SecretBench into any prompt unmasked. Your masking step must run first, exactly as in production.

**Showing improvements honestly (the result you present)**
1. Run every system on the same real samples: Rules only, detect-secrets (secrets), Raw log + LLM (CI), Raw traceback + LLM (errors), and DevGuard. The improvement you show is DevGuard against these baselines on real data.
2. Split each sample into a dev set (30) and a held-out test set (the rest). Do your error analysis and quick fixes on dev only, then report on held-out only. Tuning on the data you report is leakage and a reviewer will catch it.
3. Run it as v1, fix the top 2 to 3 failure causes you find (new secret rules, per-rule entropy thresholds, better log trimming), then run v2. Show a v1 vs v2 table on the Evaluation page. That is a real before/after improvement.
4. Report the numbers you get. If DevGuard does not beat a baseline on some metric, show that and the error analysis. Do not drop it.

**Expect lower numbers on real data. That is the honest result.** Report it, show the error analysis, and say what you changed because of it.

---

## Phase 2 CLI additions (30 min each, optional behind the dashboard)

All in `cli/main.py`. Add the global provider flag first:
```python
@app.callback()
def main(provider: str = typer.Option(None, "--provider", help="mock|gemini|openai|ollama")):
    if provider:
        os.environ["LLM_PROVIDER"] = provider
```
- `devguard status`: provider, model, RAG backend, index size, DB path, key present yes/no.
- `devguard ask "question"`: answer plus a Rich table of sources and scores.
- `devguard ci analyze <logfile|->`: cleaned size, category, root cause, fix.
- `devguard scan --staged`: scans staged files only, exit code 1 on a real secret.
- `devguard eval`: prints the benchmark tables.

```python
@app.command()
def ask(question: str):
    rag = DevGuardRAG(); rag.build_index(Path("."))
    with console.status("Retrieving and answering..."):
        result = asyncio.run(rag.query_codebase(question))
    console.print(Panel(result.answer, title="Answer"))
    t = Table("File", "Score")
    for s in result.sources: t.add_row(s.relative_path, f"{s.score:.1f}")
    console.print(t)
```

---

## Phase 2 build order (do in this order, stop when time runs out)

1. Fix the eval (0%), re-run with a real provider (needed by D3). Fix the RAG label.
2. D1 badge, then D3 evaluation page. Safest, highest value.
3. D4 CI analyzer tab.
4. D6 AST context panel.
5. D5 finding trace.
6. D2 overview and D8 seeder.
7. D7 retrieval transparency.
8. CLI `status`, `ask`, `ci analyze`, `eval`.

If you only finish items 1 to 4, you still have a strong demo: honest status, benchmark results, live CI analysis and AST-based error explanation.

## Phase 2 demo flow (about 6 minutes)

1. Overview page: four engines, stats, charts.
2. Evaluation page: show 90% vs 56.67% vs 40%, state the provider and dataset size, state the limitations.
3. CI tab: paste a log, show cleaning, category, root cause and PR comment preview.
4. Error tab: paste a traceback, show the AST context panel and the with/without toggle.
5. Findings: open one trace, show masking before the LLM.
6. Terminal: `devguard scan --staged` blocks a commit with a fake key (30 seconds).

---

# PHASE 3 (completing the project)

## P3-1. Real-data evaluation (see E1)
- Run the three real datasets (SecretBench, LogChunks, BugsInPy / PyTraceBugs) using the E1 method: baselines on the full data, LLM systems on fixed samples, dev/held-out split, v1 vs v2.
- Show synthetic and real results side by side on the Evaluation page.

## P3-2. Secret Scanner improvement
- Error analysis of every miss and false alarm.
- Add rules: JWT, PEM private keys, Google API keys (`AIza[0-9A-Za-z_-]{35}`), DB URLs with credentials, generic `password|secret|token = "..."`.
- Per-rule entropy thresholds (`min_entropy` per rule), path-based downweighting for `tests/` and docs, `.devguardignore` allowlist.
- Goal: recall near 80% without dropping below the current precision (77.78%).

## P3-3. Embedding retrieval backend
- `app/engines/rag/llamaindex_backend.py` with LlamaIndex + FAISS and `RAG_BACKEND=keyword|llamaindex`. Keep keyword as baseline.
- Dashboard: Ask tab gets a backend toggle and a side-by-side comparison view for the same question.
- Benchmark: `eval/datasets/rag_questions.csv` (25 to 30 questions, including vocabulary-mismatch ones), metrics hit@1, hit@3, MRR, latency, shown on the Evaluation page.
```bash
pip install llama-index-core llama-index-embeddings-huggingface llama-index-vector-stores-faiss faiss-cpu
```
```python
import faiss
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, StorageContext, Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.faiss import FaissVectorStore

Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")
Settings.llm = None   # retrieval only; generation stays in your LLM wrapper
docs = SimpleDirectoryReader(root, recursive=True,
        required_exts=[".py", ".md", ".yml", ".yaml", ".toml"],
        exclude=[".venv/*", "__pycache__/*", ".git/*"]).load_data()
vs = FaissVectorStore(faiss_index=faiss.IndexFlatL2(384))
index = VectorStoreIndex.from_documents(docs, storage_context=StorageContext.from_defaults(vector_store=vs))
retriever = index.as_retriever(similarity_top_k=5)
```

## P3-4. RAG inside the analyzers
- CI analyzer: extract hints from the log (failing test path, function names, missing module), retrieve the top 3 chunks, and add them to the prompt as "Relevant repository context". Switch with `CI_USE_RAG`.
- Error explainer: fall back to RAG for frames the AST resolver cannot follow.
- Evaluate with and without retrieval on 15 to 20 logs where the cause lives in repo code. Report honestly if it does not help.

## P3-5. Prompt and LLM comparison
- Prompt variants (`zero_shot`, `structured`, `few_shot`) via `PROMPT_VARIANT`, across Gemini, gpt-4o-mini and Ollama.
- Record accuracy, valid-JSON rate, latency, tokens and cost in `eval/results_matrix.csv`, with a disk cache so re-runs are free.
- Design ablations: with vs without log cleaning, with vs without masking (accuracy only; never send real secrets).
- Show the matrix on the Evaluation page.

## P3-6. CI/CD for the project itself
`.github/workflows/ci.yml` running pytest with coverage, `devguard scan .` (SARIF upload) and the eval on mock. Add `.devguardignore` entries for fixtures with fake secrets.
```yaml
name: ci
on:
  push: { branches: [main] }
  pull_request:
jobs:
  test:
    runs-on: ubuntu-latest
    env: { LLM_PROVIDER: mock }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12", cache: pip }
      - run: pip install -e . pytest pytest-asyncio pytest-cov
      - run: pytest --cov=app --cov-report=term-missing
      - run: python -m cli.main scan . --format sarif > devguard.sarif
      - uses: github/codeql-action/upload-sarif@v3
        if: always()
        with: { sarif_file: devguard.sarif }
      - run: python eval/run_experiments.py
```
Self-debugging loop: once deployed, point a `workflow_run` webhook at `/webhooks/github`, break a test on purpose, and DevGuard comments the root cause on the PR.

## P3-7. Remaining CLI and tooling
- `devguard hook install` (writes `.git/hooks/pre-commit`, refuses to overwrite without `--force`).
- `--format json|sarif` on scan (masked values only).
- `devguard demo`: scripted walkthrough (planted key blocked, CI log analyzed, traceback explained, RAG question) with `--fast`.
- Optional: AI-generated tests for `rules.py` and `classifier.py`, keeping only meaningful ones, with before/after coverage.

## P3-8. Deployment and hardening
- Dockerfile: non-root user, `$PORT`, healthcheck on `/health`. Postgres via `DATABASE_URL`. Host on Render or Railway.
- Demo repo with webhook, JSON content type, secret, events: Workflow runs and Pull requests.
- API key dependency on write endpoints (leave `/webhooks/github` on HMAC), `slowapi` rate limiting, dashboard basic auth if public, confirm `.env` was never committed.
- Prompt-injection defence: wrap logs and tracebacks in delimiters, treat them as data, keep strict JSON validation, add two tests with injected instructions.

---

# Definition of done

**Phase 2**
- [ ] Status badge shows the real provider on every page
- [ ] Evaluation page shows benchmark results with provider, date and dataset size
- [ ] Error-explainer 0% explained and fixed
- [ ] CI Analyzer tab shows cleaning, category, root cause and PR comment preview
- [ ] Error Explainer shows the AST context panel
- [ ] Findings expand to a pipeline trace with masked values only
- [ ] Overview page has stats and charts from seeded data
- [ ] RAG label corrected, retrieval panel shows scores
- [ ] CLI: `status`, `ask`, `ci analyze`, `eval` work

**Phase 3**
- [ ] Real-world datasets added and reported separately
- [ ] Secret recall near 80%, misses analyzed
- [ ] Embedding backend benchmarked against keyword retrieval, comparison in the dashboard
- [ ] RAG feeds the CI analyzer with a with/without ablation
- [ ] Prompt and LLM matrix, plus cleaning and masking ablations
- [ ] CI workflow green, self-debugging loop demonstrated
- [ ] Deployed service receives a real webhook and comments on a PR
- [ ] `devguard demo` runs clean offline
