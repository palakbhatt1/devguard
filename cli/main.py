import asyncio
import csv
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from typing import Optional
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from app.engines.errors import ErrorExplainer
from app.engines.secrets import SecretScanner
from app.llm import get_llm_client

app = typer.Typer(
    name="devguard",
    help="AI DevGuard - Secret Scanner & Error Explainer CLI",
    add_completion=False,
)
console = Console()


@app.command(name="scan")
def scan_command(
    path: str = typer.Argument(".", help="Path to file or directory to scan for secret leaks"),
    use_llm: bool = typer.Option(True, "--llm/--no-llm", help="Enable or disable LLM triage step"),
    strict: bool = typer.Option(True, "--strict/--no-strict", help="Exit with non-zero code if real secrets are found"),
    staged: bool = typer.Option(False, "--staged", help="Scan only git staged changes"),
):
    """Scan code files or git working directory for exposed secret keys and API tokens."""
    llm_client = get_llm_client() if use_llm else None
    scanner = SecretScanner(llm_client=llm_client)

    if staged:
        console.print("[bold blue][DevGuard] Secret Scanner[/bold blue] - Scanning [bold yellow]git staged changes[/bold yellow]...")
        try:
            diff_proc = subprocess.run(
                ["git", "diff", "--cached", "-U0"],
                capture_output=True, text=True, check=True
            )
            staged_diff = diff_proc.stdout
            if not staged_diff.strip():
                console.print("[bold green][OK] No staged changes to scan.[/bold green]")
                sys.exit(0)
            findings = scanner.scan_text(staged_diff, file_path="git:staged")
            if use_llm and llm_client and findings:
                findings = asyncio.run(asyncio.gather(*[scanner.triage_finding_with_llm(f) for f in findings]))
        except Exception as e:
            console.print(f"[bold red]Failed to get git staged diff: {e}[/bold red]")
            sys.exit(1)
    elif os.path.isfile(path):
        console.print(f"[bold blue][DevGuard] Secret Scanner[/bold blue] - Scanning '[bold yellow]{path}[/bold yellow]'...")
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            findings = scanner.scan_text(content, file_path=path)
            if use_llm and llm_client and findings:
                findings = asyncio.run(asyncio.gather(*[scanner.triage_finding_with_llm(f) for f in findings]))
        except Exception as e:
            console.print(f"[bold red]Error reading file {path}: {e}[/bold red]")
            sys.exit(1)
    else:
        console.print(f"[bold blue][DevGuard] Secret Scanner[/bold blue] - Scanning '[bold yellow]{path}[/bold yellow]'...")
        findings = asyncio.run(scanner.scan_directory(path, use_llm_triage=use_llm))

    real_secrets = [f for f in findings if f.is_real_secret]

    if not findings:
        console.print("[bold green][OK] Clean! No secret leaks detected.[/bold green]")
        sys.exit(0)

    table = Table(title="DevGuard Secret Findings Summary", show_header=True, header_style="bold magenta")
    table.add_column("Rule Name", style="cyan")
    table.add_column("Location", style="yellow")
    table.add_column("Masked Secret", style="bold white")
    table.add_column("Entropy", justify="right")
    table.add_column("Status", justify="center")

    for f in findings:
        status_str = "[bold red]REAL SECRET[/bold red]" if f.is_real_secret else "[dim green]Decoy/Placeholder[/dim green]"
        table.add_row(
            f.rule_name,
            f"{f.file_path}:{f.line_number}",
            f.masked_value,
            f"{f.entropy_score:.2f}",
            status_str,
        )

    console.print(table)

    if real_secrets:
        console.print(
            f"\n[bold red][ALERT] Found {len(real_secrets)} REAL secret leak(s)![/bold red] "
            "Commit blocked for security protection."
        )
        if strict:
            sys.exit(1)
    else:
        console.print("\n[bold yellow][WARN] Found candidate findings, but all classified as placeholders/decoys.[/bold yellow]")
        sys.exit(0)


@app.command(name="explain")
def explain_command(
    target: str = typer.Argument(..., help="Path to traceback file OR raw traceback text string"),
):
    """Diagnose a Python traceback string or log file and display LLM explanation."""
    console.print("[bold blue][DevGuard] Error Explainer[/bold blue]")

    traceback_text = target
    source_code = None
    if os.path.exists(target) and os.path.isfile(target):
        try:
            with open(target, "r", encoding="utf-8", errors="ignore") as f:
                traceback_text = f.read()
        except Exception as e:
            console.print(f"[bold red]Failed to read file {target}: {e}[/bold red]")
            sys.exit(1)

    llm_client = get_llm_client()
    explainer = ErrorExplainer(llm_client=llm_client)

    try:
        res = asyncio.run(explainer.explain_error(traceback_text=traceback_text, provided_source_code=source_code))
    except Exception as e:
        console.print(f"[bold red]Failed to explain exception: {e}[/bold red]")
        sys.exit(1)

    panel_content = (
        f"[bold red]Exception:[/bold red] {res.exception_type}\n"
        f"[bold yellow]Summary:[/bold yellow] {res.summary}\n\n"
        f"[bold cyan]Root Cause:[/bold cyan]\n{res.root_cause}\n\n"
        f"[bold green]Suggested Fix:[/bold green]\n{res.suggested_fix}"
    )

    if res.fixed_code_snippet:
        panel_content += f"\n\n[bold white]Fixed Code Snippet:[/bold white]\n```python\n{res.fixed_code_snippet}\n```"

    console.print(Panel(panel_content, title="[bold]AI DevGuard Error Diagnosis[/bold]", border_style="purple"))


@app.command()
def status():
    """Show current DevGuard configuration and status."""
    from app.config import get_settings
    s = get_settings()
    has_key = bool(s.LLM_API_KEY.strip())
    console.print(Panel(
        f"[bold]Provider:[/bold] {s.LLM_PROVIDER}\n"
        f"[bold]Model:[/bold] {s.LLM_MODEL}\n"
        f"[bold]RAG Backend:[/bold] keyword\n"
        f"[bold]DB:[/bold] {s.DATABASE_URL}\n"
        f"[bold]API Key:[/bold] {'present' if has_key else 'missing (mock mode)'}",
        title="DevGuard Status"
    ))


@app.command()
def ask(question: str = typer.Argument(..., help="Question to ask about your codebase")):
    """Ask DevGuard a question about your codebase using RAG."""
    from app.engines.rag.engine import DevGuardRAG
    llm_client = get_llm_client()
    rag = DevGuardRAG(workspace_root=".", llm_client=llm_client)
    with console.status("Indexing and retrieving..."):
        result = asyncio.run(rag.query_codebase(question))
    console.print(Panel(result.answer, title="Answer", border_style="cyan"))
    t = Table("File", "Score", title="Retrieved Sources", show_header=True)
    for s in result.sources:
        t.add_row(s.relative_path, f"{s.score:.1f}")
    console.print(t)


@app.command(name="ci-analyze")
def ci_analyze(logfile: str = typer.Argument(..., help="Path to CI log file, or '-' for stdin")):
    """Analyze a CI failure log file."""
    from app.engines.ci import CIFailureAnalyzer, classify_ci_failure_rules, clean_ci_log
    if logfile == "-":
        raw_log = sys.stdin.read()
    else:
        with open(logfile, "r", encoding="utf-8", errors="ignore") as f:
            raw_log = f.read()
    llm = get_llm_client()
    analyzer = CIFailureAnalyzer(llm_client=llm)
    cleaned = clean_ci_log(raw_log)
    category = classify_ci_failure_rules(cleaned)
    console.print(f"[bold]Log size:[/bold] {len(raw_log)} → {len(cleaned)} bytes ({round(100*(1-len(cleaned)/max(len(raw_log),1)))}% reduced)")
    console.print(f"[bold]Rule category:[/bold] [yellow]{category}[/yellow]")
    with console.status("Analyzing with LLM..."):
        result = asyncio.run(analyzer.analyze_log(raw_log=raw_log))
    console.print(Panel(
        f"[bold]Category:[/bold] {result.failure_category}\n[bold]Root Cause:[/bold] {result.root_cause}\n[bold]Fix:[/bold] {result.suggested_fix}",
        title="CI Analysis", border_style="yellow"
    ))


@app.command(name="eval")
def run_eval():
    """Print evaluation benchmark results from CSV files."""
    for name, label in [("eval/results_secrets.csv", "Secrets"), ("eval/results_ci.csv", "CI"), ("eval/results_errors.csv", "Errors")]:
        p = pathlib.Path(name)
        if not p.exists():
            console.print(f"[red]Missing: {name}[/red]")
            continue
        with open(p, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            continue
        t = Table(*rows[0].keys(), title=label)
        for row in rows:
            t.add_row(*row.values())
        console.print(t)


if __name__ == "__main__":
    app()
