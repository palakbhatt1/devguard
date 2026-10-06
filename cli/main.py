import asyncio
import os
import sys
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
):
    """Scan code files or git working directory for exposed secret keys and API tokens."""
    console.print(f"[bold blue][DevGuard] Secret Scanner[/bold blue] - Scanning '[bold yellow]{path}[/bold yellow]'...")

    llm_client = get_llm_client() if use_llm else None
    scanner = SecretScanner(llm_client=llm_client)

    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            findings = scanner.scan_text(content, file_path=path)
            if use_llm and llm_client:
                findings = asyncio.run(asyncio.gather(*[scanner.triage_finding_with_llm(f) for f in findings]))
        except Exception as e:
            console.print(f"[bold red]Error reading file {path}: {e}[/bold red]")
            sys.exit(1)
    else:
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


if __name__ == "__main__":
    app()
