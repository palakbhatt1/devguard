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
                logger.error(f"Error calling LLM provider endpoint: {e}")
                raise e


class GeminiLLMClient(OpenAICompatibleLLMClient):
    """Google Gemini LLM client using Google AI Studio OpenAI-compatible endpoint."""

    def __init__(self, api_key: str, model: str = "gemini-3.1-flash-lite", base_url: str = ""):
        endpoint = base_url or "https://generativelanguage.googleapis.com/v1beta/openai/v1/chat/completions"
        super().__init__(api_key=api_key, model=model, base_url=endpoint)


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

            return ErrorExplanationResult(
                exception_type=exc_type,
                summary=f"An unhandled {exc_type} occurred during execution.",
                root_cause=f"The code triggered a {exc_type} due to invalid state or missing key.",
                suggested_fix="Verify inputs and add safety checks before dereferencing values.",
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
    model = model_override or settings.LLM_MODEL or "gemini-3.1-flash-lite"
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
