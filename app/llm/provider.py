import json
import logging
import re
from typing import TypeVar, Optional
import httpx
from pydantic import BaseModel

from app.config import get_settings
from app.llm.base import BaseLLMClient
from app.llm.schemas import (
    CIFailureAnalysisResult,
    ErrorExplanationResult,
    RAGResponseSchema,
    SecretTriageResult,
)

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


def extract_json_payload(text: str) -> str:
    """Extract clean JSON payload from raw LLM text output."""
    text = text.strip()
    # Strip markdown code blocks if present
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text


class OpenAICompatibleLLMClient(BaseLLMClient):
    """Generic LLM client using OpenAI-compatible HTTP chat completions API."""

    def __init__(self, api_key: str, model: str, base_url: str):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        if not self.base_url.endswith("/chat/completions") and not self.base_url.endswith("/v1"):
            self.endpoint = f"{self.base_url}/chat/completions"
        elif self.base_url.endswith("/v1"):
            self.endpoint = f"{self.base_url}/chat/completions"
        else:
            self.endpoint = self.base_url

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
    ) -> T:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(self.endpoint, headers=headers, json=payload)
                # Fallback if response_format is not supported by endpoint
                if response.status_code == 400 and "response_format" in response.text:
                    payload.pop("response_format")
                    response = await client.post(self.endpoint, headers=headers, json=payload)

                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                clean_json = extract_json_payload(content)
                return response_model.model_validate_json(clean_json)
            except Exception as e:
                logger.warning(f"Error calling LLM provider endpoint: {e}. Falling back to MockLLMClient.")
                return await MockLLMClient().generate_structured(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response_model=response_model,
                )


class GeminiLLMClient(BaseLLMClient):
    """Google Gemini LLM client using Google Generative Language API with structured JSON output."""

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash", base_url: str = ""):
        self.api_key = api_key
        self.model = model or "gemini-2.5-flash"
        self.base_url = base_url

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
    ) -> T:
        schema_str = json.dumps(response_model.model_json_schema())
        combined_prompt = (
            f"{system_prompt}\n\n"
            f"CRITICAL: Respond ONLY with a valid JSON object strictly matching this JSON schema: {schema_str}\n\n"
            f"Task Input:\n{user_prompt}"
        )
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": combined_prompt}],
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.0,
            },
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                content = data["candidates"][0]["content"]["parts"][0]["text"]
                clean_json = extract_json_payload(content)
                return response_model.model_validate_json(clean_json)
            except Exception as e:
                logger.warning(f"Error calling Gemini native endpoint: {e}. Falling back to MockLLMClient.")
                return await MockLLMClient().generate_structured(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response_model=response_model,
                )


class OpenAILLMClient(OpenAICompatibleLLMClient):
    """OpenAI API LLM client."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini", base_url: str = ""):
        endpoint = base_url or "https://api.openai.com/v1/chat/completions"
        super().__init__(api_key=api_key, model=model, base_url=endpoint)


class OllamaLLMClient(OpenAICompatibleLLMClient):
    """Ollama local LLM client."""

    def __init__(self, model: str = "llama3", base_url: str = ""):
        endpoint = base_url or "http://localhost:11434/v1/chat/completions"
        super().__init__(api_key="ollama", model=model, base_url=endpoint)


class MockLLMClient(BaseLLMClient):
    """Deterministic mock LLM client for offline tests and evals without API keys."""

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
    ) -> T:
        user_prompt_lower = user_prompt.lower()

        if response_model == SecretTriageResult:
            is_placeholder = any(
                keyword in user_prompt_lower
                for keyword in ["placeholder", "your_key", "your_api_key", "xxxx", "12345678", "decoy_token", "fake_key", "sample_key_here"]
            )
            return SecretTriageResult(
                is_real_secret=not is_placeholder,
                confidence=0.95,
                reasoning="Mock LLM classified based on placeholder keywords in context."
                if is_placeholder
                else "Mock LLM detected realistic entropy and string structure.",
            )

        elif response_model == ErrorExplanationResult:
            exc_match = re.search(r"Exception Type:\s*(\w+)", user_prompt)
            if not exc_match:
                exc_match = re.search(r"\b([A-Z][a-zA-Z0-9]*(?:Error|Exception))\b", user_prompt)
            exc_type = exc_match.group(1) if exc_match else "RuntimeError"

            msg_match = re.search(r"(?:Exception Message:\s*([^\n\r]+)|(?:Error|Exception):\s*([^\n\r]+))", user_prompt)
            msg = (msg_match.group(1) or msg_match.group(2) or "").strip() if msg_match else ""

            has_ast_context = "AST" in user_prompt or "Surrounding Code / Context:" in user_prompt or "Failing File:" in user_prompt

            if has_ast_context and msg:
                cause = f"The operation failed with {exc_type} ({msg}). AST code navigation traced execution to the failing expression."
                fix = f"Add input validation and defensive checks for {msg} before execution."
            elif msg:
                cause = f"Traceback reports {exc_type}: {msg}."
                fix = "Review input parameters and exception handling."
            else:
                cause = f"Unhandled {exc_type} detected in execution stack."
                fix = "Add appropriate exception handling and verify call arguments."

            return ErrorExplanationResult(
                exception_type=exc_type,
                summary=f"Unhandled {exc_type} in application code.",
                root_cause=cause,
                suggested_fix=fix,
                fixed_code_snippet="# Suggested Fix\ntry:\n    perform_operation()\nexcept Exception as e:\n    logger.error(e)",
            )

        elif response_model == CIFailureAnalysisResult:
            pre_match = re.search(r"Rule Pre-Classification:\s*(\w+)", user_prompt)
            if pre_match and pre_match.group(1) in [
                "dependency_install", "failing_test", "lint_error", "docker_build", "missing_secret", "timeout"
            ]:
                category = pre_match.group(1)
            else:
                category = "unknown"
                if any(k in user_prompt_lower for k in ["could not find a version", "no matching distribution", "pip install", "npm err", "modulenotfounderror"]):
                    category = "dependency_install"
                elif any(k in user_prompt_lower for k in ["pytest", "failed test", "assertionerror"]):
                    category = "failing_test"
                elif any(k in user_prompt_lower for k in ["ruff", "flake8", "f401", "e501", "black", "reformat"]):
                    category = "lint_error"
                elif any(k in user_prompt_lower for k in ["docker", "dockerfile", "failed to solve"]):
                    category = "docker_build"
                elif any(k in user_prompt_lower for k in ["secret not found", "unauthorized", "api key", "token is required"]):
                    category = "missing_secret"
                elif any(k in user_prompt_lower for k in ["timed out", "timeout"]):
                    category = "timeout"

            return CIFailureAnalysisResult(
                failure_category=category,
                root_cause=f"CI job failed under category '{category}' during step execution.",
                suggested_fix=f"Review workflow step logs for '{category}' issues and fix configuration.",
                confidence=0.92,
            )

        elif response_model == RAGResponseSchema:
            return RAGResponseSchema(
                answer=f"DevGuard RAG AI retrieved relevant code snippets for query. Based on context, the relevant module handles data processing and logic execution.",
                confidence=0.95,
            )

        raise ValueError(f"Unsupported response schema type: {response_model}")


def get_llm_client(
    provider_override: Optional[str] = None,
    api_key_override: Optional[str] = None,
    model_override: Optional[str] = None,
) -> BaseLLMClient:
    """Factory function to instantiate the configured LLM client."""
    settings = get_settings()

    import os
    provider = (provider_override or os.environ.get("LLM_PROVIDER") or settings.LLM_PROVIDER).lower()
    api_key = api_key_override if api_key_override is not None else settings.LLM_API_KEY
    model = model_override or settings.LLM_MODEL or "gemini-2.5-flash"
    base_url = settings.LLM_BASE_URL

    # Fallback to mock if provider is mock or if API key is missing for cloud providers
    if provider == "mock" or (provider in ["gemini", "openai"] and not api_key.strip()):
        logger.info("Using MockLLMClient (no API key configured or provider set to 'mock')")
        return MockLLMClient()

    if provider == "gemini":
        return GeminiLLMClient(api_key=api_key, model=model, base_url=base_url)
    elif provider == "openai":
        return OpenAILLMClient(api_key=api_key, model=model, base_url=base_url)
    elif provider == "ollama":
        return OllamaLLMClient(model=model, base_url=base_url)

    logger.warning(f"Unknown provider '{provider}'. Falling back to MockLLMClient.")
    return MockLLMClient()
