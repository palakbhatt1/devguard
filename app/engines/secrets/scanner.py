from dataclasses import dataclass
import os
from typing import List, Optional

from app.engines.secrets.allowlist import is_known_placeholder, is_path_ignored
from app.engines.secrets.entropy import shannon_entropy
from app.engines.secrets.masking import mask_secret
from app.engines.secrets.rules import SECRET_RULES, SecretRule
from app.llm.base import BaseLLMClient
from app.llm.prompts import SECRET_TRIAGE_SYSTEM_PROMPT, SECRET_TRIAGE_USER_PROMPT
from app.llm.schemas import SecretTriageResult


@dataclass
class RawFinding:
    file_path: str
    line_number: int
    rule_name: str
    raw_value: str
    masked_value: str
    entropy_score: float
    context_snippet: str
    is_real_secret: bool = True
    reasoning: Optional[str] = None


class SecretScanner:
    """Secret Scanner engine using Regex rules, Shannon Entropy, Masking, and LLM triage."""

    def __init__(self, llm_client: Optional[BaseLLMClient] = None):
        self.llm_client = llm_client

    def scan_text(
        self,
        text: str,
        file_path: str = "inline_code",
    ) -> List[RawFinding]:
        """Scan a single text string line by line for secret leaks."""
        findings: List[RawFinding] = []
        lines = text.splitlines()

        for idx, line in enumerate(lines, start=1):
            for rule in SECRET_RULES:
                for match in rule.pattern.finditer(line):
                    raw_val = match.group(1) if match.groups() else match.group(0)

                    # Compute entropy
                    entropy = shannon_entropy(raw_val)

                    # Ignore if entropy is below threshold (unless it's a fixed format like PEM key header)
                    if rule.min_entropy > 0 and entropy < rule.min_entropy:
                        continue

                    # Mask secret value immediately
                    masked = mask_secret(raw_val)

                    # Quick local heuristic check for obvious placeholders
                    is_placeholder = is_known_placeholder(raw_val)
                    initial_is_real = not is_placeholder

                    # Extract context snippet (1 line above, current line, 1 line below)
                    start_ctx = max(0, idx - 2)
                    end_ctx = min(len(lines), idx + 1)
                    raw_ctx = "\n".join(lines[start_ctx:end_ctx])
                    context_snippet = raw_ctx.replace(raw_val, masked)

                    findings.append(
                        RawFinding(
                            file_path=file_path,
                            line_number=idx,
                            rule_name=rule.name,
                            raw_value=raw_val,
                            masked_value=masked,
                            entropy_score=entropy,
                            context_snippet=context_snippet,
                            is_real_secret=initial_is_real,
                            reasoning="Known placeholder keyword match"
                            if is_placeholder
                            else "Regex rule matched high entropy string",
                        )
                    )

        return findings

    async def triage_finding_with_llm(self, finding: RawFinding) -> RawFinding:
        """Use LLM triage to assess whether finding is a real secret vs decoy.

        CRITICAL SECURITY GUARANTEE: Only the masked_value and context with masked string
        is sent to the LLM.
        """
        if not self.llm_client:
            return finding

        # Replace any raw occurrences in context snippet with masked string before sending to LLM
        safe_snippet = finding.context_snippet.replace(finding.raw_value, finding.masked_value)
        finding.context_snippet = safe_snippet
        finding.context_snippet = safe_snippet

        user_prompt = (
            SECRET_TRIAGE_USER_PROMPT
            .replace("{rule_name}", str(finding.rule_name))
            .replace("{masked_value}", str(finding.masked_value))
            .replace("{entropy_score}", f"{finding.entropy_score:.2f}")
            .replace("{context_snippet}", str(safe_snippet))
        )

        try:
            res: SecretTriageResult = await self.llm_client.generate_structured(
                system_prompt=SECRET_TRIAGE_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                response_model=SecretTriageResult,
            )
            finding.is_real_secret = res.is_real_secret
            finding.reasoning = res.reasoning
        except Exception as e:
            finding.reasoning = f"LLM triage fallback due to error: {e}"

        return finding

    async def scan_directory(
        self,
        directory_path: str,
        use_llm_triage: bool = True,
    ) -> List[RawFinding]:
        """Recursively scan a directory for secret leaks."""
        all_findings: List[RawFinding] = []

        for root, dirs, files in os.walk(directory_path):
            # Exclude ignored directories
            dirs[:] = [d for d in dirs if not is_path_ignored(d)]

            for file in files:
                rel_path = os.path.relpath(os.path.join(root, file), directory_path)
                if is_path_ignored(rel_path):
                    continue

                full_file_path = os.path.join(root, file)
                try:
                    with open(full_file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()

                    file_findings = self.scan_text(content, file_path=rel_path)
                    all_findings.extend(file_findings)
                except Exception:
                    continue

        if use_llm_triage and self.llm_client:
            triaged_findings = []
            for f in all_findings:
                triaged = await self.triage_finding_with_llm(f)
                triaged_findings.append(triaged)
            return triaged_findings

        return all_findings
