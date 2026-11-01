import pytest
import os
from app.engines.errors.graph import ASTNavigator
from app.engines.rag.engine import DevGuardRAG, RAGQueryResult
from app.llm.provider import MockLLMClient


def test_ast_navigator_enclosing_scope():
    nav = ASTNavigator(workspace_root=".")
    # Test on app/engines/secrets/masking.py line 7
    masking_file = os.path.abspath("app/engines/secrets/masking.py")
    if os.path.exists(masking_file):
        enc_func, enc_class = nav.find_enclosing_scope(masking_file, 7)
        assert enc_func == "mask_secret" or enc_func is not None


def test_ast_navigator_get_semantic_context():
    nav = ASTNavigator(workspace_root=".")
    explainer_file = os.path.abspath("app/engines/errors/explainer.py")
    if os.path.exists(explainer_file):
        ctx = nav.get_semantic_context(explainer_file, line_number=20)
        assert ctx.failing_file == explainer_file
        assert "SEMANTIC CODE NAVIGATION CONTEXT" in ctx.formatted_context_block


@pytest.mark.anyio
async def test_rag_engine_indexing_and_query():
    llm = MockLLMClient()
    rag = DevGuardRAG(workspace_root=".", llm_client=llm)
    rag.build_index()

    # Retrieve chunks for a known query
    chunks = rag.retrieve("secret masking", top_k=2)
    assert len(chunks) > 0
    assert "mask" in chunks[0].content.lower() or "secret" in chunks[0].content.lower()
    assert hasattr(chunks[0], "matched_terms")

    # Query codebase
    res: RAGQueryResult = await rag.query_codebase("How are secrets masked?")
    assert res.query == "How are secrets masked?"
    assert len(res.sources) > 0
    assert "Keyword RAG" in res.engine_used
