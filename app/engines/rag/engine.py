import os
import re
from dataclasses import dataclass, field
from typing import List, Optional
from app.llm.base import BaseLLMClient


@dataclass
class RAGChunk:
    file_path: str
    relative_path: str
    chunk_index: int
    content: str
    score: float = 0.0
    matched_terms: list = field(default_factory=list)
    matched_terms: list = field(default_factory=list)


@dataclass
class RAGQueryResult:
    query: str
    answer: str
    sources: List[RAGChunk] = field(default_factory=list)
    engine_used: str = "Keyword RAG"


class DevGuardRAG:
    """RAG-based Codebase & Security Q&A Engine using keyword retrieval and LLM synthesis."""

    def __init__(self, workspace_root: str = ".", llm_client: Optional[BaseLLMClient] = None):
        self.workspace_root = os.path.abspath(workspace_root)
        self.llm_client = llm_client
        self._chunks: List[RAGChunk] = []
        self._is_indexed = False

    def build_index(self):
        """Index workspace python files, markdown docs, and configuration files."""
        chunks: List[RAGChunk] = []
        allowed_exts = {".py", ".md", ".yml", ".yaml", ".toml", ".csv"}
        ignore_dirs = {".venv", "__pycache__", ".git", ".pytest_cache", "brain", ".gemini"}

        for root, dirs, files in os.walk(self.workspace_root):
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in allowed_exts:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, self.workspace_root)
                    try:
                        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                            text = f.read()

                        # Break into ~50 line / paragraph chunks
                        paragraphs = text.split("\n\n")
                        chunk_idx = 0
                        for p in paragraphs:
                            p_clean = p.strip()
                            if len(p_clean) > 30:
                                chunks.append(
                                    RAGChunk(
                                        file_path=full_path,
                                        relative_path=rel_path,
                                        chunk_index=chunk_idx,
                                        content=p_clean,
                                    )
                                )
                                chunk_idx += 1
                    except Exception:
                        pass

        self._chunks = chunks
        self._is_indexed = True

    def retrieve(self, query: str, top_k: int = 4) -> List[RAGChunk]:
        """Search indexed codebase chunks for relevant query snippets."""
        if not self._is_indexed:
            self.build_index()

        stop_words = {
            "how", "does", "do", "what", "where", "why", "is", "are", "the", "a",
            "an", "in", "on", "of", "to", "for", "with", "it", "this", "that",
            "works", "work", "give", "me", "tell", "explain", "about", "can", "you"
        }

        all_terms = re.findall(r"\w+", query.lower())
        meaningful_terms = set(t for t in all_terms if t not in stop_words and len(t) > 1)

        if not meaningful_terms:
            meaningful_terms = set(all_terms)

        scored_chunks: List[RAGChunk] = []

        for chunk in self._chunks:
            chunk_content_lower = chunk.content.lower()
            chunk_words = set(re.findall(r"\w+", chunk_content_lower))
            overlap = len(meaningful_terms.intersection(chunk_words))

            if overlap > 0:
                # Path bonus: if query terms appear in relative path (e.g. 'masking', 'secrets')
                path_words = set(re.findall(r"\w+", chunk.relative_path.lower()))
                path_overlap = len(meaningful_terms.intersection(path_words))

                # Phrase bonus for multi-word matches (e.g. 'secret masking')
                phrase_bonus = 3.0 if query.lower() in chunk_content_lower else 0.0

                score = (overlap * 2.0) + (path_overlap * 4.0) + phrase_bonus
                chunk_copy = RAGChunk(
                    file_path=chunk.file_path,
                    relative_path=chunk.relative_path,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    score=score,
                    matched_terms=list(meaningful_terms.intersection(chunk_words)),
                )
                scored_chunks.append(chunk_copy)

        scored_chunks.sort(key=lambda x: x.score, reverse=True)
        return scored_chunks[:top_k]

    async def query_codebase(self, query: str) -> RAGQueryResult:
        """Answer developer question using retrieved codebase context."""
        retrieved_chunks = self.retrieve(query, top_k=4)

        if not retrieved_chunks:
            return RAGQueryResult(
                query=query,
                answer="No relevant code or documentation found in the workspace matching your query.",
                sources=[],
                engine_used="Keyword RAG",
            )

        context_blocks = []
        for i, c in enumerate(retrieved_chunks, 1):
            context_blocks.append(f"--- Source {i}: [{c.relative_path}] ---\n{c.content}")

        context_str = "\n\n".join(context_blocks)

        system_prompt = (
            "You are DevGuard RAG AI Assistant. Answer developer questions about the codebase accurately "
            "based ONLY on the provided source code chunks and documentation. Be concise, technical, and helpful."
        )

        user_prompt = (
            f"Developer Query: {query}\n\n"
            f"Retrieved Codebase Context:\n{context_str}\n\n"
            "Provide a clear, detailed answer referencing the specific source files."
        )

        if self.llm_client:
            from app.llm.schemas import RAGResponseSchema
            try:
                res = await self.llm_client.generate_structured(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response_model=RAGResponseSchema,
                )
                answer_text = res.answer
            except Exception as e:
                answer_text = (
                    f"Retrieved Context from [{retrieved_chunks[0].relative_path}]:\n\n"
                    f"{retrieved_chunks[0].content[:400]}..."
                )
        else:
            answer_text = (
                f"Based on [{retrieved_chunks[0].relative_path}], the query matches codebase context:\n"
                f"{retrieved_chunks[0].content[:200]}..."
            )

        return RAGQueryResult(
            query=query,
            answer=answer_text,
            sources=retrieved_chunks,
            engine_used="Keyword RAG",
        )
