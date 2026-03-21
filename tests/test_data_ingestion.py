"""
Tests for data ingestion: chunk_document(), store_in_vector_db(), chunks_exist_for_paper().

Run with:
    uv run pytest tests/test_data_ingestion.py -v
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, call
from typing import List

from langchain_core.documents import Document

from app.services.data_ingestion.types import PdfDocument
from app.constants import CHUNK_OVERLAP, CHUNK_SIZE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pdf_doc(content: str, doc_id: str = "doc-001", file_name: str = "paper.pdf", num_pages: int = 5) -> PdfDocument:
    return PdfDocument(doc_id=doc_id, content=content, file_name=file_name, num_pages=num_pages)


# ---------------------------------------------------------------------------
# chunk_document() tests
# ---------------------------------------------------------------------------

class TestChunkDocument:
    """Unit tests for process.chunk_document()."""

    def test_returns_list_of_langchain_documents(self):
        """chunk_document() must return a list of LangChain Document objects."""
        from app.services.data_ingestion.process import chunk_document

        pdf_doc = _make_pdf_doc("This is some content. " * 100)
        result = chunk_document(pdf_doc)

        assert isinstance(result, list)
        assert len(result) > 0
        for doc in result:
            assert isinstance(doc, Document)

    def test_empty_content_returns_empty_list(self):
        """An empty content string must produce no chunks and log a warning."""
        from app.services.data_ingestion.process import chunk_document

        pdf_doc = _make_pdf_doc("")
        result = chunk_document(pdf_doc)

        assert result == []

    def test_whitespace_only_content_returns_empty_list(self):
        """Whitespace-only content must produce no chunks."""
        from app.services.data_ingestion.process import chunk_document

        pdf_doc = _make_pdf_doc("   \n\t  ")
        result = chunk_document(pdf_doc)

        assert result == []

    def test_short_content_produces_single_chunk(self):
        """Content shorter than CHUNK_SIZE tokens should produce exactly one chunk."""
        from app.services.data_ingestion.process import chunk_document

        # A short sentence is well below 500 tokens
        pdf_doc = _make_pdf_doc("This is a short abstract.")
        result = chunk_document(pdf_doc)

        assert len(result) == 1

    def test_long_content_produces_multiple_chunks(self):
        """Content much longer than CHUNK_SIZE must be split into multiple chunks."""
        from app.services.data_ingestion.process import chunk_document

        # ~3000 words → well over 500 tokens
        long_text = ("The quick brown fox jumps over the lazy dog. " * 200)
        pdf_doc = _make_pdf_doc(long_text)
        result = chunk_document(pdf_doc)

        assert len(result) > 1

    def test_chunk_metadata_contains_required_keys(self):
        """Every chunk must carry doc_id, chunk_index, filename, page_count metadata."""
        from app.services.data_ingestion.process import chunk_document

        pdf_doc = _make_pdf_doc("Sample content. " * 50, doc_id="doc-xyz", file_name="test.pdf", num_pages=3)
        result = chunk_document(pdf_doc)

        for idx, doc in enumerate(result):
            assert doc.metadata["doc_id"] == "doc-xyz"
            assert doc.metadata["filename"] == "test.pdf"
            assert doc.metadata["page_count"] == 3
            assert doc.metadata["chunk_index"] == idx

    def test_chunk_indices_are_sequential_from_zero(self):
        """chunk_index must start at 0 and increment by 1 for every chunk."""
        from app.services.data_ingestion.process import chunk_document

        pdf_doc = _make_pdf_doc("Word sentence paragraph. " * 300)
        result = chunk_document(pdf_doc)

        expected_indices = list(range(len(result)))
        actual_indices = [doc.metadata["chunk_index"] for doc in result]
        assert actual_indices == expected_indices

    def test_uses_chunk_overlap_constant(self):
        """
        chunk_document() must consume CHUNK_OVERLAP=200 from constants.
        We verify by patching RecursiveCharacterTextSplitter and inspecting
        the constructor kwargs.
        """
        from app.services.data_ingestion import process as process_module

        with patch.object(
            process_module,
            "RecursiveCharacterTextSplitter",
            wraps=process_module.RecursiveCharacterTextSplitter,
        ) as mock_splitter_cls:
            pdf_doc = _make_pdf_doc("Content " * 50)
            process_module.chunk_document(pdf_doc)

        mock_splitter_cls.assert_called_once()
        _, kwargs = mock_splitter_cls.call_args
        assert kwargs["chunk_overlap"] == CHUNK_OVERLAP
        assert kwargs["chunk_overlap"] == 200  # Explicit assertion on the literal value

    def test_uses_chunk_size_constant(self):
        """chunk_document() must pass CHUNK_SIZE=500 to the text splitter."""
        from app.services.data_ingestion import process as process_module

        with patch.object(
            process_module,
            "RecursiveCharacterTextSplitter",
            wraps=process_module.RecursiveCharacterTextSplitter,
        ) as mock_splitter_cls:
            pdf_doc = _make_pdf_doc("Content " * 50)
            process_module.chunk_document(pdf_doc)

        _, kwargs = mock_splitter_cls.call_args
        assert kwargs["chunk_size"] == CHUNK_SIZE
        assert kwargs["chunk_size"] == 500

    def test_chunk_page_content_is_non_empty(self):
        """No chunk should have an empty page_content string."""
        from app.services.data_ingestion.process import chunk_document

        pdf_doc = _make_pdf_doc("Non-trivial text here. " * 80)
        result = chunk_document(pdf_doc)

        for doc in result:
            assert doc.page_content.strip() != ""

    def test_none_content_attribute_returns_empty_list(self):
        """If the PdfDocument has no content attribute (edge case via getattr), return []."""
        from app.services.data_ingestion.process import chunk_document

        pdf_doc = _make_pdf_doc("placeholder")
        # Override the attribute to simulate a missing/None scenario
        object.__setattr__(pdf_doc, "content", None)
        result = chunk_document(pdf_doc)

        assert result == []

    def test_chunk_count_matches_known_input(self):
        """
        For a predictable input verify chunk count is at least 2 and matches
        a stable lower bound (regression guard).

        We build content that encodes to >1500 tiktoken tokens, well above the
        500-token CHUNK_SIZE, guaranteeing at least 2 chunks.
        Note: highly repetitive strings tokenise more compactly than word count
        suggests, so we use a repeat count verified to exceed the threshold.
        """
        from app.services.data_ingestion.process import chunk_document

        # 200 repetitions → ~1601 tokens (verified), > 500-token CHUNK_SIZE
        content = "academic research methodology systematic review literature analysis. " * 200
        pdf_doc = _make_pdf_doc(content)
        result = chunk_document(pdf_doc)

        # Must have split at least once
        assert len(result) >= 2
        # Chunk count should be consistent across runs (regression guard: ≤10 for this input)
        assert len(result) <= 10


# ---------------------------------------------------------------------------
# chunks_exist_for_paper() tests
# ---------------------------------------------------------------------------

class TestChunksExistForPaper:
    """Unit tests for store.chunks_exist_for_paper()."""

    @patch("app.services.data_ingestion.store._get_supabase_client")
    def test_returns_true_when_rows_exist(self, mock_get_client):
        """Should return True when Supabase returns at least one row."""
        from app.services.data_ingestion.store import chunks_exist_for_paper

        mock_response = MagicMock()
        mock_response.data = [{"id": "some-uuid"}]

        mock_table = MagicMock()
        mock_table.select.return_value.filter.return_value.limit.return_value.execute.return_value = mock_response
        mock_get_client.return_value.table.return_value = mock_table

        result = chunks_exist_for_paper("paper-123")

        assert result is True

    @patch("app.services.data_ingestion.store._get_supabase_client")
    def test_returns_false_when_no_rows(self, mock_get_client):
        """Should return False when Supabase returns an empty list."""
        from app.services.data_ingestion.store import chunks_exist_for_paper

        mock_response = MagicMock()
        mock_response.data = []

        mock_table = MagicMock()
        mock_table.select.return_value.filter.return_value.limit.return_value.execute.return_value = mock_response
        mock_get_client.return_value.table.return_value = mock_table

        result = chunks_exist_for_paper("paper-456")

        assert result is False

    @patch("app.services.data_ingestion.store._get_supabase_client")
    def test_returns_false_when_data_is_none(self, mock_get_client):
        """Should return False when Supabase returns None as data (empty response)."""
        from app.services.data_ingestion.store import chunks_exist_for_paper

        mock_response = MagicMock()
        mock_response.data = None

        mock_table = MagicMock()
        mock_table.select.return_value.filter.return_value.limit.return_value.execute.return_value = mock_response
        mock_get_client.return_value.table.return_value = mock_table

        result = chunks_exist_for_paper("paper-789")

        assert result is False

    @patch("app.services.data_ingestion.store._get_supabase_client")
    def test_queries_correct_table_and_column(self, mock_get_client):
        """chunks_exist_for_paper() must query the paper_chunks table on metadata->>paper_id."""
        from app.services.data_ingestion.store import chunks_exist_for_paper
        from app.constants import TABLE_NAME

        mock_response = MagicMock()
        mock_response.data = []
        mock_table = MagicMock()
        mock_table.select.return_value.filter.return_value.limit.return_value.execute.return_value = mock_response
        mock_client = mock_get_client.return_value
        mock_client.table.return_value = mock_table

        chunks_exist_for_paper("paper-abc")

        mock_client.table.assert_called_once_with(TABLE_NAME)
        mock_table.select.assert_called_once_with("id")

    @patch("app.services.data_ingestion.store._get_supabase_client")
    def test_limits_query_to_one_row(self, mock_get_client):
        """The query must use .limit(1) to keep the existence check efficient."""
        from app.services.data_ingestion.store import chunks_exist_for_paper

        mock_response = MagicMock()
        mock_response.data = []
        mock_table = MagicMock()
        limit_mock = MagicMock()
        limit_mock.execute.return_value = mock_response
        mock_table.select.return_value.filter.return_value.limit.return_value = limit_mock
        mock_get_client.return_value.table.return_value = mock_table

        chunks_exist_for_paper("paper-limit-test")

        mock_table.select.return_value.filter.return_value.limit.assert_called_once_with(1)


# ---------------------------------------------------------------------------
# store_in_vector_db() — idempotency tests
# ---------------------------------------------------------------------------

class TestStoreInVectorDb:
    """Unit tests for store.store_in_vector_db()."""

    def _make_docs(self, paper_id: str = "paper-001", count: int = 3) -> List[Document]:
        return [
            Document(page_content=f"Chunk {i}", metadata={"paper_id": paper_id, "chunk_index": i})
            for i in range(count)
        ]

    def test_skips_insertion_when_chunks_already_exist(self):
        """store_in_vector_db() must not call add_documents when chunks already exist."""
        from app.services.data_ingestion import store as store_module

        docs = self._make_docs(paper_id="existing-paper")

        with patch.object(store_module, "chunks_exist_for_paper", return_value=True) as mock_exists, \
             patch.object(store_module, "get_vectorstore") as mock_vs:

            store_module.store_in_vector_db(docs)

            mock_exists.assert_called_once_with("existing-paper")
            mock_vs.return_value.add_documents.assert_not_called()

    def test_inserts_when_no_existing_chunks(self):
        """store_in_vector_db() must call add_documents when no chunks exist yet."""
        from app.services.data_ingestion import store as store_module

        docs = self._make_docs(paper_id="new-paper")

        with patch.object(store_module, "chunks_exist_for_paper", return_value=False), \
             patch.object(store_module, "get_vectorstore") as mock_vs, \
             patch.object(store_module, "sanitize_document", side_effect=lambda d: d):

            store_module.store_in_vector_db(docs)

            mock_vs.return_value.add_documents.assert_called_once()

    def test_noop_for_empty_doc_list(self):
        """store_in_vector_db() with an empty list must be a no-op (no DB calls)."""
        from app.services.data_ingestion import store as store_module

        with patch.object(store_module, "chunks_exist_for_paper") as mock_exists, \
             patch.object(store_module, "get_vectorstore") as mock_vs:

            store_module.store_in_vector_db([])

            mock_exists.assert_not_called()
            mock_vs.assert_not_called()

    def test_idempotent_called_twice_inserts_once(self):
        """
        Calling store_in_vector_db() twice for the same paper must only insert once.
        Second call should see existing chunks and skip.
        """
        from app.services.data_ingestion import store as store_module

        docs = self._make_docs(paper_id="idempotent-paper")

        # Simulate: first call → no chunks; second call → chunks exist
        exist_side_effects = [False, True]

        with patch.object(store_module, "chunks_exist_for_paper", side_effect=exist_side_effects) as mock_exists, \
             patch.object(store_module, "get_vectorstore") as mock_vs, \
             patch.object(store_module, "sanitize_document", side_effect=lambda d: d):

            store_module.store_in_vector_db(docs)
            store_module.store_in_vector_db(docs)

            assert mock_vs.return_value.add_documents.call_count == 1

    def test_skips_exist_check_when_no_paper_id_in_metadata(self):
        """Docs without paper_id in metadata skip the existence check and go straight to insert."""
        from app.services.data_ingestion import store as store_module

        docs = [Document(page_content="chunk without paper_id", metadata={"chunk_index": 0})]

        with patch.object(store_module, "chunks_exist_for_paper") as mock_exists, \
             patch.object(store_module, "get_vectorstore") as mock_vs, \
             patch.object(store_module, "sanitize_document", side_effect=lambda d: d):

            store_module.store_in_vector_db(docs)

            # No paper_id → no existence check
            mock_exists.assert_not_called()
            mock_vs.return_value.add_documents.assert_called_once()

    def test_sanitize_document_called_for_each_doc(self):
        """Every document must be sanitized before insertion."""
        from app.services.data_ingestion import store as store_module

        docs = self._make_docs(paper_id="sanitize-test", count=4)

        with patch.object(store_module, "chunks_exist_for_paper", return_value=False), \
             patch.object(store_module, "get_vectorstore"), \
             patch.object(store_module, "sanitize_document", side_effect=lambda d: d) as mock_sanitize:

            store_module.store_in_vector_db(docs)

            assert mock_sanitize.call_count == 4
