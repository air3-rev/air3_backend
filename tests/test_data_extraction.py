"""
Tests for data extraction: extract_paper_data(), extract_paper_data_with_full_text(),
refine_relevant_chunks() / refine chain JSON structure.

Run with:
    uv run pytest tests/test_data_extraction.py -v
"""

from __future__ import annotations

import json
import pytest
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_chunk(chunk_id: str = "c1", text: str = "sample content", similarity: float = 0.9) -> Dict[str, Any]:
    return {
        "id": chunk_id,
        "text": text,
        "metadata": {"paper_id": "paper-001", "chunk_index": 0},
        "similarity": similarity,
    }


_VALID_REFINED_JSON = json.dumps({
    "summary": "A concise summary.",
    "key_points": ["Point A: finding one", "Point B: finding two"],
    "extracted_items": [{"item": "value"}],
    "sources": [{"id": "c1", "reason": "relevant"}],
})


# ---------------------------------------------------------------------------
# extract_paper_data() — orchestration tests
# ---------------------------------------------------------------------------

class TestExtractPaperData:
    """Tests for main.extract_paper_data()."""

    @patch("app.services.data_extraction.main.refine_relevant_chunks")
    @patch("app.services.data_extraction.main.fetch_paper_chunks")
    def test_calls_fetch_then_refine(self, mock_fetch, mock_refine):
        """extract_paper_data() must call fetch_paper_chunks then refine_relevant_chunks."""
        from app.services.data_extraction.main import extract_paper_data

        fake_chunks = [_make_chunk("c1"), _make_chunk("c2")]
        mock_fetch.return_value = fake_chunks
        mock_refine.return_value = {"summary": "ok", "key_points": [], "extracted_items": [], "sources": []}

        result = extract_paper_data(label="Methods", k=5, paper_id="paper-001")

        mock_fetch.assert_called_once_with("Methods", k=5, paper_id="paper-001")
        mock_refine.assert_called_once_with(fake_chunks)

    @patch("app.services.data_extraction.main.refine_relevant_chunks")
    @patch("app.services.data_extraction.main.fetch_paper_chunks")
    def test_returns_refine_output_directly(self, mock_fetch, mock_refine):
        """extract_paper_data() must return exactly what refine_relevant_chunks returns."""
        from app.services.data_extraction.main import extract_paper_data

        expected = {"summary": "test summary", "key_points": ["kp1"], "extracted_items": [], "sources": []}
        mock_fetch.return_value = []
        mock_refine.return_value = expected

        result = extract_paper_data(label="Results", k=3, paper_id="paper-002")

        assert result == expected

    @patch("app.services.data_extraction.main.refine_relevant_chunks")
    @patch("app.services.data_extraction.main.fetch_paper_chunks")
    def test_passes_k_and_paper_id_to_fetch(self, mock_fetch, mock_refine):
        """k and paper_id args must be forwarded verbatim to fetch_paper_chunks."""
        from app.services.data_extraction.main import extract_paper_data

        mock_fetch.return_value = []
        mock_refine.return_value = {"summary": "", "key_points": [], "extracted_items": [], "sources": []}

        extract_paper_data(label="Background", k=10, paper_id="paper-xyz")

        mock_fetch.assert_called_once_with("Background", k=10, paper_id="paper-xyz")

    @patch("app.services.data_extraction.main.refine_relevant_chunks")
    @patch("app.services.data_extraction.main.fetch_paper_chunks")
    def test_default_k_is_five(self, mock_fetch, mock_refine):
        """Default k parameter must be 5."""
        from app.services.data_extraction.main import extract_paper_data

        mock_fetch.return_value = []
        mock_refine.return_value = {"summary": "", "key_points": [], "extracted_items": [], "sources": []}

        extract_paper_data(label="Methods")

        _, kwargs = mock_fetch.call_args
        assert kwargs["k"] == 5


# ---------------------------------------------------------------------------
# extract_paper_data_with_full_text() — label processing tests
# ---------------------------------------------------------------------------

class TestExtractPaperDataWithFullText:
    """Tests for main.extract_paper_data_with_full_text()."""

    def _mock_llm_response(self, payload: Dict[str, Any]) -> MagicMock:
        """Return a mock LLM message whose .content is a JSON string."""
        mock_msg = MagicMock()
        mock_msg.content = json.dumps(payload)
        return mock_msg

    @patch("app.services.data_extraction.main.ChatOpenAI")
    def test_returns_dict_keyed_by_labels(self, mock_llm_cls):
        """Result dict must contain an entry for each requested label."""
        from app.services.data_extraction.main import extract_paper_data_with_full_text

        labels = ["Methods", "Results"]
        llm_payload = {
            "Methods": {"summary": "method summary", "key_points": [], "extracted_items": [], "sources": []},
            "Results": {"summary": "results summary", "key_points": [], "extracted_items": [], "sources": []},
        }
        mock_instance = mock_llm_cls.return_value
        mock_instance.bind.return_value.invoke.return_value = self._mock_llm_response(llm_payload)

        result = extract_paper_data_with_full_text(labels, full_text="Paper content here.")

        assert set(result.keys()) == {"Methods", "Results"}

    @patch("app.services.data_extraction.main.ChatOpenAI")
    def test_result_has_required_fields(self, mock_llm_cls):
        """Every label entry must have summary, key_points, extracted_items, sources."""
        from app.services.data_extraction.main import extract_paper_data_with_full_text

        labels = ["Conclusions"]
        llm_payload = {
            "Conclusions": {
                "summary": "The study concludes X.",
                "key_points": ["Finding 1"],
                "extracted_items": [],
                "sources": ["p.5"],
            }
        }
        mock_instance = mock_llm_cls.return_value
        mock_instance.bind.return_value.invoke.return_value = self._mock_llm_response(llm_payload)

        result = extract_paper_data_with_full_text(labels, full_text="conclusion content")
        entry = result["Conclusions"]

        assert "summary" in entry
        assert "key_points" in entry
        assert "extracted_items" in entry
        assert "sources" in entry

    @patch("app.services.data_extraction.main.ChatOpenAI")
    def test_na_summary_normalises_other_fields(self, mock_llm_cls):
        """When summary is N/A, key_points / extracted_items / sources must be cleared."""
        from app.services.data_extraction.main import extract_paper_data_with_full_text

        labels = ["Funding"]
        llm_payload = {
            "Funding": {
                "summary": "N/A",
                "key_points": ["some leftover"],
                "extracted_items": ["leftover item"],
                "sources": ["p.2"],
            }
        }
        mock_instance = mock_llm_cls.return_value
        mock_instance.bind.return_value.invoke.return_value = self._mock_llm_response(llm_payload)

        result = extract_paper_data_with_full_text(labels, full_text="text")
        entry = result["Funding"]

        assert entry["summary"] == "N/A"
        assert entry["key_points"] == []
        assert entry["extracted_items"] == []
        assert entry["sources"] == []

    @patch("app.services.data_extraction.main.ChatOpenAI")
    def test_label_key_strips_colon_prefix(self, mock_llm_cls):
        """Labels like 'Methods: Describe methods' should match the key 'Methods' in the response."""
        from app.services.data_extraction.main import extract_paper_data_with_full_text

        labels = ["Methods: Describe the methods used"]
        llm_payload = {
            "Methods": {
                "summary": "regression analysis",
                "key_points": [],
                "extracted_items": [],
                "sources": [],
            }
        }
        mock_instance = mock_llm_cls.return_value
        mock_instance.bind.return_value.invoke.return_value = self._mock_llm_response(llm_payload)

        result = extract_paper_data_with_full_text(labels, full_text="paper text")

        assert "Methods: Describe the methods used" in result
        assert result["Methods: Describe the methods used"]["summary"] == "regression analysis"

    @patch("app.services.data_extraction.main.ChatOpenAI")
    def test_llm_error_returns_error_dict_for_all_labels(self, mock_llm_cls):
        """If the LLM raises an exception, all labels must get an error-summary entry."""
        from app.services.data_extraction.main import extract_paper_data_with_full_text

        labels = ["A", "B", "C"]
        mock_instance = mock_llm_cls.return_value
        mock_instance.bind.return_value.invoke.side_effect = RuntimeError("LLM unavailable")

        result = extract_paper_data_with_full_text(labels, full_text="content")

        assert set(result.keys()) == {"A", "B", "C"}
        for label in labels:
            assert result[label]["summary"] == "Error extracting data"
            assert result[label]["key_points"] == []

    @patch("app.services.data_extraction.main.ChatOpenAI")
    def test_empty_labels_list_returns_empty_dict(self, mock_llm_cls):
        """Passing an empty labels list must return an empty dict."""
        from app.services.data_extraction.main import extract_paper_data_with_full_text

        llm_payload = {}
        mock_instance = mock_llm_cls.return_value
        mock_instance.bind.return_value.invoke.return_value = self._mock_llm_response(llm_payload)

        result = extract_paper_data_with_full_text([], full_text="content")

        assert result == {}

    @patch("app.services.data_extraction.main.ChatOpenAI")
    def test_not_applicable_summary_variants_normalised(self, mock_llm_cls):
        """'Not applicable', 'Not mentioned', 'Not reported', '' should all normalise to N/A."""
        from app.services.data_extraction.main import extract_paper_data_with_full_text

        not_applicable_variants = ["Not applicable", "Not mentioned", "Not reported", ""]
        for variant in not_applicable_variants:
            labels = ["Label"]
            llm_payload = {
                "Label": {"summary": variant, "key_points": ["kp"], "extracted_items": ["item"], "sources": ["s"]}
            }
            mock_instance = mock_llm_cls.return_value
            mock_instance.bind.return_value.invoke.return_value = self._mock_llm_response(llm_payload)

            result = extract_paper_data_with_full_text(labels, full_text="text")
            entry = result["Label"]

            assert entry["summary"] == "N/A", f"Expected N/A for variant '{variant}'"
            assert entry["key_points"] == []
            assert entry["extracted_items"] == []
            assert entry["sources"] == []


# ---------------------------------------------------------------------------
# refine_relevant_chunks() — chain behaviour tests
# ---------------------------------------------------------------------------

class TestRefineRelevantChunks:
    """Tests for refine.refine_relevant_chunks()."""

    def test_empty_chunks_returns_empty_structure(self):
        """Empty chunk list must return default empty dict without calling the LLM."""
        from app.services.data_extraction.refine import refine_relevant_chunks

        result = refine_relevant_chunks([])

        assert result == {"summary": "", "key_points": [], "extracted_items": [], "sources": []}

    @patch("app.services.data_extraction.refine._llm")
    def test_single_chunk_invokes_initial_chain_only(self, mock_llm_factory):
        """A single chunk must trigger only the initial chain, not the refine loop."""
        from app.services.data_extraction.refine import refine_relevant_chunks

        mock_llm = MagicMock()
        mock_llm_factory.return_value = mock_llm

        fake_response = MagicMock()
        fake_response.content = _VALID_REFINED_JSON

        # initial_chain (prompt | llm) → chain.invoke() called once
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = fake_response

        with patch("app.services.data_extraction.refine.PromptTemplate") as mock_pt:
            # Both from_template calls return something whose __or__ returns mock_chain
            mock_pt.from_template.return_value.partial.return_value.__or__ = MagicMock(return_value=mock_chain)

            result = refine_relevant_chunks([_make_chunk()])

        # Only one invoke for one doc
        assert mock_chain.invoke.call_count == 1

    @patch("app.services.data_extraction.refine._llm")
    def test_multiple_chunks_invoke_chain_n_times(self, mock_llm_factory):
        """N chunks must produce N chain.invoke() calls (1 initial + N-1 refine)."""
        from app.services.data_extraction.refine import refine_relevant_chunks

        mock_llm = MagicMock()
        mock_llm_factory.return_value = mock_llm

        fake_response = MagicMock()
        fake_response.content = _VALID_REFINED_JSON

        mock_chain = MagicMock()
        mock_chain.invoke.return_value = fake_response

        chunks = [_make_chunk(f"c{i}", f"text {i}") for i in range(4)]

        with patch("app.services.data_extraction.refine.PromptTemplate") as mock_pt:
            mock_pt.from_template.return_value.partial.return_value.__or__ = MagicMock(return_value=mock_chain)

            result = refine_relevant_chunks(chunks)

        assert mock_chain.invoke.call_count == 4  # 1 initial + 3 refine

    @patch("app.services.data_extraction.refine._llm")
    def test_result_has_all_required_keys(self, mock_llm_factory):
        """Output dict must always include summary, key_points, extracted_items, sources."""
        from app.services.data_extraction.refine import refine_relevant_chunks

        mock_llm = MagicMock()
        mock_llm_factory.return_value = mock_llm

        fake_response = MagicMock()
        fake_response.content = _VALID_REFINED_JSON

        mock_chain = MagicMock()
        mock_chain.invoke.return_value = fake_response

        with patch("app.services.data_extraction.refine.PromptTemplate") as mock_pt:
            mock_pt.from_template.return_value.partial.return_value.__or__ = MagicMock(return_value=mock_chain)

            result = refine_relevant_chunks([_make_chunk()])

        assert "summary" in result
        assert "key_points" in result
        assert "extracted_items" in result
        assert "sources" in result

    @patch("app.services.data_extraction.refine._llm")
    def test_key_points_are_deduplicated(self, mock_llm_factory):
        """Duplicate key_points must be removed from the final result."""
        from app.services.data_extraction.refine import refine_relevant_chunks

        mock_llm = MagicMock()
        mock_llm_factory.return_value = mock_llm

        duplicated_json = json.dumps({
            "summary": "A summary.",
            "key_points": ["duplicate point", "unique point", "Duplicate Point"],
            "extracted_items": [],
            "sources": [],
        })
        fake_response = MagicMock()
        fake_response.content = duplicated_json

        mock_chain = MagicMock()
        mock_chain.invoke.return_value = fake_response

        with patch("app.services.data_extraction.refine.PromptTemplate") as mock_pt:
            mock_pt.from_template.return_value.partial.return_value.__or__ = MagicMock(return_value=mock_chain)

            result = refine_relevant_chunks([_make_chunk()])

        # Dedup is case-insensitive
        lower_points = [kp.lower() for kp in result["key_points"]]
        assert len(lower_points) == len(set(lower_points))

    @patch("app.services.data_extraction.refine._llm")
    def test_invalid_json_from_llm_raises(self, mock_llm_factory):
        """If the LLM returns non-JSON, refine_relevant_chunks must raise an exception."""
        from app.services.data_extraction.refine import refine_relevant_chunks

        mock_llm = MagicMock()
        mock_llm_factory.return_value = mock_llm

        fake_response = MagicMock()
        fake_response.content = "This is not valid JSON at all!"

        mock_chain = MagicMock()
        mock_chain.invoke.return_value = fake_response

        with patch("app.services.data_extraction.refine.PromptTemplate") as mock_pt:
            mock_pt.from_template.return_value.partial.return_value.__or__ = MagicMock(return_value=mock_chain)

            with pytest.raises(Exception):
                refine_relevant_chunks([_make_chunk()])

    @patch("app.services.data_extraction.refine._llm")
    def test_sources_are_deduplicated_by_id(self, mock_llm_factory):
        """Duplicate source entries with the same id must be collapsed to one."""
        from app.services.data_extraction.refine import refine_relevant_chunks

        mock_llm = MagicMock()
        mock_llm_factory.return_value = mock_llm

        dup_sources_json = json.dumps({
            "summary": "summary",
            "key_points": [],
            "extracted_items": [],
            "sources": [
                {"id": "chunk-1", "reason": "first reference"},
                {"id": "chunk-1", "reason": "second reference"},
                {"id": "CHUNK-1", "reason": "case variant"},
                {"id": "chunk-2", "reason": "unique"},
            ],
        })
        fake_response = MagicMock()
        fake_response.content = dup_sources_json

        mock_chain = MagicMock()
        mock_chain.invoke.return_value = fake_response

        with patch("app.services.data_extraction.refine.PromptTemplate") as mock_pt:
            mock_pt.from_template.return_value.partial.return_value.__or__ = MagicMock(return_value=mock_chain)

            result = refine_relevant_chunks([_make_chunk()])

        source_ids = [s["id"].lower() for s in result["sources"]]
        assert len(source_ids) == len(set(source_ids))

    @patch("app.services.data_extraction.refine._llm")
    def test_key_points_capped_at_fifteen(self, mock_llm_factory):
        """key_points must be limited to a maximum of 15 entries."""
        from app.services.data_extraction.refine import refine_relevant_chunks

        mock_llm = MagicMock()
        mock_llm_factory.return_value = mock_llm

        many_kp_json = json.dumps({
            "summary": "summary",
            "key_points": [f"unique point {i}" for i in range(25)],
            "extracted_items": [],
            "sources": [],
        })
        fake_response = MagicMock()
        fake_response.content = many_kp_json

        mock_chain = MagicMock()
        mock_chain.invoke.return_value = fake_response

        with patch("app.services.data_extraction.refine.PromptTemplate") as mock_pt:
            mock_pt.from_template.return_value.partial.return_value.__or__ = MagicMock(return_value=mock_chain)

            result = refine_relevant_chunks([_make_chunk()])

        assert len(result["key_points"]) <= 15


# ---------------------------------------------------------------------------
# fetch_paper_chunks() — Supabase RPC delegation tests
# ---------------------------------------------------------------------------

class TestFetchPaperChunks:
    """Tests for fetch.fetch_paper_chunks()."""

    @patch("app.services.data_extraction.fetch._get_supabase")
    @patch("app.services.data_extraction.fetch._get_embeddings")
    def test_empty_label_returns_empty_list(self, mock_embed, mock_sb):
        """An empty / whitespace-only label must short-circuit and return []."""
        from app.services.data_extraction.fetch import fetch_paper_chunks

        result = fetch_paper_chunks("   ", k=5, paper_id="paper-001")

        assert result == []
        mock_embed.assert_not_called()
        mock_sb.assert_not_called()

    @patch("app.services.data_extraction.fetch._get_supabase")
    @patch("app.services.data_extraction.fetch._get_embeddings")
    def test_calls_rpc_with_match_chunks(self, mock_embed, mock_sb):
        """fetch_paper_chunks() must call the match_chunks RPC."""
        from app.services.data_extraction.fetch import fetch_paper_chunks

        mock_embed.return_value.embed_query.return_value = [0.1] * 1536

        mock_rpc_response = MagicMock()
        mock_rpc_response.data = []
        mock_sb.return_value.rpc.return_value.execute.return_value = mock_rpc_response

        fetch_paper_chunks("Methods", k=3, paper_id="paper-rpc")

        mock_sb.return_value.rpc.assert_called_once()
        rpc_name = mock_sb.return_value.rpc.call_args[0][0]
        assert rpc_name == "match_chunks"

    @patch("app.services.data_extraction.fetch._get_supabase")
    @patch("app.services.data_extraction.fetch._get_embeddings")
    def test_normalises_rows_to_chunk_format(self, mock_embed, mock_sb):
        """Raw Supabase rows must be normalised to id/text/metadata/similarity dicts."""
        from app.services.data_extraction.fetch import fetch_paper_chunks

        mock_embed.return_value.embed_query.return_value = [0.0] * 1536

        raw_rows = [
            {"id": "uuid-1", "content": "chunk text one", "metadata": {"paper_id": "p1"}, "similarity": 0.92},
            {"id": "uuid-2", "content": "chunk text two", "metadata": {}, "similarity": 0.85},
        ]
        mock_rpc_response = MagicMock()
        mock_rpc_response.data = raw_rows
        mock_sb.return_value.rpc.return_value.execute.return_value = mock_rpc_response

        result = fetch_paper_chunks("Results", k=2, paper_id="p1")

        assert len(result) == 2
        assert result[0]["id"] == "uuid-1"
        assert result[0]["text"] == "chunk text one"
        assert result[0]["similarity"] == 0.92

    @patch("app.services.data_extraction.fetch._get_supabase")
    @patch("app.services.data_extraction.fetch._get_embeddings")
    def test_rpc_exception_propagates(self, mock_embed, mock_sb):
        """If the Supabase RPC raises, the exception must propagate to the caller."""
        from app.services.data_extraction.fetch import fetch_paper_chunks

        mock_embed.return_value.embed_query.return_value = [0.0] * 1536
        mock_sb.return_value.rpc.return_value.execute.side_effect = ConnectionError("Supabase down")

        with pytest.raises(ConnectionError):
            fetch_paper_chunks("Methods", k=5, paper_id="paper-x")
