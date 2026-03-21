"""
Tests for ReviewGenerationService:
  - generate_section_content() builds correct context and returns a response
  - Missing section raises ValueError
  - _prepare_extracted_data_summary() formats data correctly
  - _generate_section_content() invokes the LLM chain correctly

Run with:
    uv run pytest tests/test_review_generation.py -v
"""

from __future__ import annotations

import pytest
import asyncio
from datetime import datetime
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch, call

from app.schemas.review_generation import (
    GenerateSectionRequest,
    GenerateSectionResponse,
    SectionContext,
    SubsectionContext,
    SectionData,
    PaperExtractedData,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_section_data(
    section_id: str = "sec-001",
    title: str = "Introduction",
    description: str = "Provide background",
    subsections: List[Dict[str, str]] = None,
) -> SectionData:
    return SectionData(
        id=section_id,
        title=title,
        description=description,
        subsections=subsections or [],
    )


def _make_extracted_data(
    paper_id: str = "paper-001",
    label_name: str = "Methods",
    data: Dict[str, Any] = None,
) -> PaperExtractedData:
    return PaperExtractedData(
        paper_id=paper_id,
        label_name=label_name,
        data=data or {"summary": "regression", "key_points": ["kp1"]},
        created_at=datetime(2025, 1, 1),
    )


def _make_section_context(
    extracted_data: List[PaperExtractedData] = None,
    previous_sections: Dict[str, str] = None,
) -> SectionContext:
    return SectionContext(
        section=_make_section_data(),
        assigned_papers=["paper-001", "paper-002"],
        extracted_data=extracted_data or [],
        previous_sections_content=previous_sections or {},
        previous_subsections_content={},
    )


def _make_subsection_context(
    extracted_data: List[PaperExtractedData] = None,
    section_content: str = "",
) -> SubsectionContext:
    return SubsectionContext(
        section=_make_section_data(),
        subsection={"id": "sub-001", "title": "Sub A", "description": "Detail of sub A"},
        assigned_papers=["paper-001"],
        extracted_data=extracted_data or [],
        section_content=section_content,
        previous_subsections_content={},
    )


# ---------------------------------------------------------------------------
# _prepare_extracted_data_summary() — pure formatting
# ---------------------------------------------------------------------------

class TestPrepareExtractedDataSummary:
    """Tests for ReviewGenerationService._prepare_extracted_data_summary()."""

    def _make_service(self):
        with patch("app.services.review_generation.main.ChatOpenAI"):
            from app.services.review_generation.main import ReviewGenerationService
            return ReviewGenerationService()

    def test_empty_list_returns_no_data_message(self):
        """Empty extracted_data list must return the 'No extracted data' fallback string."""
        svc = self._make_service()
        result = svc._prepare_extracted_data_summary([])
        assert result == "No extracted data available for assigned papers."

    def test_groups_entries_by_label(self):
        """Entries with the same label must be grouped under a single label heading."""
        svc = self._make_service()
        data = [
            _make_extracted_data("paper-1", "Methods"),
            _make_extracted_data("paper-2", "Methods"),
            _make_extracted_data("paper-3", "Results"),
        ]
        result = svc._prepare_extracted_data_summary(data)

        # Methods should appear once as a heading
        assert result.count("Methods:") == 1
        assert result.count("Results:") == 1

    def test_includes_paper_ids_in_output(self):
        """Each paper entry must appear with 'Paper <id>' in the summary."""
        svc = self._make_service()
        data = [_make_extracted_data("paper-xyz", "Background")]
        result = svc._prepare_extracted_data_summary(data)
        assert "Paper paper-xyz" in result

    def test_limits_to_five_papers_per_label(self):
        """No more than 5 paper entries per label should appear in the summary text."""
        svc = self._make_service()
        data = [_make_extracted_data(f"paper-{i}", "Methods") for i in range(8)]
        result = svc._prepare_extracted_data_summary(data)

        # Should see the truncation note for the extra 3 papers
        assert "3 more papers" in result

    def test_exactly_five_papers_no_truncation_note(self):
        """Exactly 5 papers per label should not trigger a truncation note."""
        svc = self._make_service()
        data = [_make_extracted_data(f"paper-{i}", "Methods") for i in range(5)]
        result = svc._prepare_extracted_data_summary(data)
        assert "more papers" not in result

    def test_output_is_newline_separated_string(self):
        """The summary must be a non-empty string with newline separation."""
        svc = self._make_service()
        data = [_make_extracted_data()]
        result = svc._prepare_extracted_data_summary(data)
        assert isinstance(result, str)
        assert "\n" in result

    def test_multiple_labels_all_appear(self):
        """Every distinct label must appear as a heading in the output."""
        svc = self._make_service()
        labels = ["Alpha", "Beta", "Gamma"]
        data = [_make_extracted_data("p1", lbl) for lbl in labels]
        result = svc._prepare_extracted_data_summary(data)
        for label in labels:
            assert f"{label}:" in result


# ---------------------------------------------------------------------------
# _generate_section_content() — LLM chain invocation
# ---------------------------------------------------------------------------

class TestGenerateSectionContentInternal:
    """Tests for ReviewGenerationService._generate_section_content() (async)."""

    def _make_service(self, mock_llm=None):
        with patch("app.services.review_generation.main.ChatOpenAI") as mock_cls:
            if mock_llm:
                mock_cls.return_value = mock_llm
            from app.services.review_generation.main import ReviewGenerationService
            svc = ReviewGenerationService()
            svc.llm = mock_llm or MagicMock()
        return svc

    @pytest.mark.asyncio
    async def test_invokes_chain_with_section_title(self):
        """The LLM chain must receive the section title in its input dict."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "  Generated academic content.  "
        mock_chain = AsyncMock(return_value=mock_response)

        with patch("app.services.review_generation.main.ChatOpenAI"):
            from app.services.review_generation.main import ReviewGenerationService
            svc = ReviewGenerationService()
            svc.llm = mock_llm

        with patch("app.services.review_generation.main.PromptTemplate") as mock_pt:
            mock_pt.return_value.__or__ = MagicMock(return_value=MagicMock(ainvoke=mock_chain))

            context = _make_section_context()
            result = await svc._generate_section_content(context)

        call_kwargs = mock_chain.call_args[0][0]
        assert call_kwargs["section_title"] == "Introduction"

    @pytest.mark.asyncio
    async def test_strips_whitespace_from_result(self):
        """The returned content must have leading/trailing whitespace stripped."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "   Content with surrounding spaces.   "
        mock_chain = AsyncMock(return_value=mock_response)

        with patch("app.services.review_generation.main.ChatOpenAI"):
            from app.services.review_generation.main import ReviewGenerationService
            svc = ReviewGenerationService()
            svc.llm = mock_llm

        with patch("app.services.review_generation.main.PromptTemplate") as mock_pt:
            mock_pt.return_value.__or__ = MagicMock(return_value=MagicMock(ainvoke=mock_chain))

            context = _make_section_context()
            result = await svc._generate_section_content(context)

        assert result == "Content with surrounding spaces."

    @pytest.mark.asyncio
    async def test_includes_previous_context_when_present(self):
        """When previous_sections_content is non-empty, the prompt must include it."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "generated"
        captured_calls = []

        async def capture_invoke(kwargs):
            captured_calls.append(kwargs)
            return mock_response

        with patch("app.services.review_generation.main.ChatOpenAI"):
            from app.services.review_generation.main import ReviewGenerationService
            svc = ReviewGenerationService()
            svc.llm = mock_llm

        with patch("app.services.review_generation.main.PromptTemplate") as mock_pt:
            mock_pt.return_value.__or__ = MagicMock(
                return_value=MagicMock(ainvoke=AsyncMock(side_effect=capture_invoke))
            )

            context = _make_section_context(
                previous_sections={"sec-prev": "Prior section content here."}
            )
            await svc._generate_section_content(context)

        assert len(captured_calls) == 1
        assert captured_calls[0]["previous_context"] != ""

    @pytest.mark.asyncio
    async def test_subsections_rendered_in_prompt(self):
        """Subsection titles and descriptions must appear in the prompt variables."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "section content"
        captured_calls = []

        async def capture_invoke(kwargs):
            captured_calls.append(kwargs)
            return mock_response

        with patch("app.services.review_generation.main.ChatOpenAI"):
            from app.services.review_generation.main import ReviewGenerationService
            svc = ReviewGenerationService()
            svc.llm = mock_llm

        section = SectionData(
            id="sec-001",
            title="Literature Overview",
            description="Overview of literature",
            subsections=[
                {"id": "s1", "title": "Sub One", "description": "first sub"},
                {"id": "s2", "title": "Sub Two", "description": "second sub"},
            ],
        )
        context = SectionContext(
            section=section,
            assigned_papers=[],
            extracted_data=[],
            previous_sections_content={},
            previous_subsections_content={},
        )

        with patch("app.services.review_generation.main.PromptTemplate") as mock_pt:
            mock_pt.return_value.__or__ = MagicMock(
                return_value=MagicMock(ainvoke=AsyncMock(side_effect=capture_invoke))
            )
            await svc._generate_section_content(context)

        assert "Sub One" in captured_calls[0]["subsections"]
        assert "Sub Two" in captured_calls[0]["subsections"]


# ---------------------------------------------------------------------------
# generate_section_content() — high-level: context building + missing section
# ---------------------------------------------------------------------------

class TestGenerateSectionContentHighLevel:
    """Integration-style tests for ReviewGenerationService.generate_section_content()."""

    def _make_service(self):
        with patch("app.services.review_generation.main.ChatOpenAI"):
            from app.services.review_generation.main import ReviewGenerationService
            return ReviewGenerationService()

    @pytest.mark.asyncio
    async def test_missing_section_raises_value_error(self):
        """When the section does not exist in Supabase, a ValueError must be raised."""
        svc = self._make_service()

        with patch("app.services.review_generation.main._get_supabase") as mock_sb:
            # Simulate section not found: single() returns data=None
            mock_section_response = MagicMock()
            mock_section_response.data = None
            mock_sb.return_value.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = mock_section_response

            request = GenerateSectionRequest(
                review_id="rev-001",
                section_id="nonexistent-section",
            )

            with pytest.raises(ValueError, match="nonexistent-section"):
                await svc.generate_section_content(request)

    @pytest.mark.asyncio
    async def test_returns_generate_section_response(self):
        """A successful call must return a GenerateSectionResponse."""
        svc = self._make_service()

        with patch.object(svc, "_build_section_context", new_callable=AsyncMock) as mock_build, \
             patch.object(svc, "_generate_section_content", new_callable=AsyncMock) as mock_gen:

            mock_build.return_value = _make_section_context()
            mock_gen.return_value = "Generated section text."

            request = GenerateSectionRequest(
                review_id="rev-001",
                section_id="sec-001",
            )

            response = await svc.generate_section_content(request)

        assert isinstance(response, GenerateSectionResponse)
        assert response.content == "Generated section text."
        assert response.section_id == "sec-001"

    @pytest.mark.asyncio
    async def test_no_subsection_id_calls_section_builder(self):
        """Without a subsection_id, the section builder and section generator are used."""
        svc = self._make_service()

        with patch.object(svc, "_build_section_context", new_callable=AsyncMock) as mock_section_build, \
             patch.object(svc, "_build_subsection_context", new_callable=AsyncMock) as mock_sub_build, \
             patch.object(svc, "_generate_section_content", new_callable=AsyncMock) as mock_gen, \
             patch.object(svc, "_generate_subsection_content", new_callable=AsyncMock) as mock_sub_gen:

            mock_section_build.return_value = _make_section_context()
            mock_gen.return_value = "section content"

            request = GenerateSectionRequest(review_id="rev-1", section_id="sec-1")
            await svc.generate_section_content(request)

            mock_section_build.assert_called_once()
            mock_gen.assert_called_once()
            mock_sub_build.assert_not_called()
            mock_sub_gen.assert_not_called()

    @pytest.mark.asyncio
    async def test_with_subsection_id_calls_subsection_builder(self):
        """With a subsection_id, the subsection builder and subsection generator are used."""
        svc = self._make_service()

        with patch.object(svc, "_build_section_context", new_callable=AsyncMock) as mock_section_build, \
             patch.object(svc, "_build_subsection_context", new_callable=AsyncMock) as mock_sub_build, \
             patch.object(svc, "_generate_section_content", new_callable=AsyncMock) as mock_gen, \
             patch.object(svc, "_generate_subsection_content", new_callable=AsyncMock) as mock_sub_gen:

            mock_sub_build.return_value = _make_subsection_context()
            mock_sub_gen.return_value = "subsection content"

            request = GenerateSectionRequest(
                review_id="rev-1",
                section_id="sec-1",
                subsection_id="sub-1",
            )
            response = await svc.generate_section_content(request)

            mock_sub_build.assert_called_once()
            mock_sub_gen.assert_called_once()
            mock_section_build.assert_not_called()
            mock_gen.assert_not_called()

            assert response.subsection_id == "sub-1"

    @pytest.mark.asyncio
    async def test_response_metadata_contains_papers_count(self):
        """Response metadata must include papers_count reflecting the assigned papers."""
        svc = self._make_service()

        context = _make_section_context()
        context = SectionContext(
            section=_make_section_data(),
            assigned_papers=["p1", "p2", "p3"],
            extracted_data=[],
            previous_sections_content={},
            previous_subsections_content={},
        )

        with patch.object(svc, "_build_section_context", new_callable=AsyncMock, return_value=context), \
             patch.object(svc, "_generate_section_content", new_callable=AsyncMock, return_value="content"):

            request = GenerateSectionRequest(review_id="rev-1", section_id="sec-1")
            response = await svc.generate_section_content(request)

        assert response.metadata["papers_count"] == 3

    @pytest.mark.asyncio
    async def test_missing_subsection_raises_value_error(self):
        """When a subsection_id is provided but the subsection is not found, ValueError is raised."""
        svc = self._make_service()

        with patch("app.services.review_generation.main._get_supabase") as mock_sb:
            call_count = 0

            def table_side_effect(name):
                nonlocal call_count
                mock_query = MagicMock()
                mock_response = MagicMock()

                call_count += 1
                if call_count == 1:
                    # First table call: section found
                    mock_response.data = {"id": "sec-1", "title": "Intro", "description": "desc"}
                else:
                    # Second table call: subsection NOT found
                    mock_response.data = None

                mock_query.select.return_value.eq.return_value.single.return_value.execute.return_value = mock_response
                return mock_query

            mock_sb.return_value.table.side_effect = table_side_effect

            request = GenerateSectionRequest(
                review_id="rev-001",
                section_id="sec-1",
                subsection_id="nonexistent-sub",
            )

            with pytest.raises(ValueError, match="nonexistent-sub"):
                await svc.generate_section_content(request)

    @pytest.mark.asyncio
    async def test_generate_section_content_propagates_llm_exception(self):
        """If the LLM chain raises, the exception must propagate from generate_section_content."""
        svc = self._make_service()

        with patch.object(svc, "_build_section_context", new_callable=AsyncMock) as mock_build, \
             patch.object(svc, "_generate_section_content", new_callable=AsyncMock) as mock_gen:

            mock_build.return_value = _make_section_context()
            mock_gen.side_effect = RuntimeError("OpenAI timeout")

            request = GenerateSectionRequest(review_id="rev-1", section_id="sec-1")

            with pytest.raises(RuntimeError, match="OpenAI timeout"):
                await svc.generate_section_content(request)


# ---------------------------------------------------------------------------
# _build_section_context() — Supabase query structure
# ---------------------------------------------------------------------------

class TestBuildSectionContext:
    """Tests for ReviewGenerationService._build_section_context()."""

    def _make_service(self):
        with patch("app.services.review_generation.main.ChatOpenAI"):
            from app.services.review_generation.main import ReviewGenerationService
            return ReviewGenerationService()

    @pytest.mark.asyncio
    async def test_raises_value_error_for_unknown_section(self):
        """_build_section_context() must raise ValueError if section is not found."""
        svc = self._make_service()

        with patch("app.services.review_generation.main._get_supabase") as mock_sb:
            mock_not_found = MagicMock()
            mock_not_found.data = None
            mock_sb.return_value.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = mock_not_found

            with pytest.raises(ValueError):
                await svc._build_section_context("rev-1", "bad-section-id")

    @pytest.mark.asyncio
    async def test_builds_context_with_correct_section(self):
        """_build_section_context() must populate section from the Supabase result."""
        svc = self._make_service()

        section_row = {"id": "sec-001", "title": "Methodology", "description": "Covers methods"}
        subsections_rows = [{"id": "sub-1", "title": "Sub", "description": "sub desc"}]
        papers_rows = [{"id": "paper-1"}]
        labels_rows = []

        with patch("app.services.review_generation.main._get_supabase") as mock_sb:
            mock_client = mock_sb.return_value

            def table_handler(table_name):
                mock_q = MagicMock()
                if table_name == "structures":
                    # Handle both .eq('id', ...).single() and .eq('parent_id', ...).execute()
                    single_resp = MagicMock()
                    single_resp.data = section_row
                    multi_resp = MagicMock()
                    multi_resp.data = subsections_rows

                    mock_q.select.return_value.eq.return_value.single.return_value.execute.return_value = single_resp
                    mock_q.select.return_value.eq.return_value.execute.return_value = multi_resp
                elif table_name == "papers":
                    papers_resp = MagicMock()
                    papers_resp.data = papers_rows
                    mock_q.select.return_value.eq.return_value.eq.return_value.execute.return_value = papers_resp
                elif table_name == "labels":
                    labels_resp = MagicMock()
                    labels_resp.data = labels_rows
                    mock_q.select.return_value.eq.return_value.execute.return_value = labels_resp
                return mock_q

            mock_client.table.side_effect = table_handler

            context = await svc._build_section_context("rev-1", "sec-001")

        assert context.section.title == "Methodology"
        assert context.section.id == "sec-001"
        assert "paper-1" in context.assigned_papers

    @pytest.mark.asyncio
    async def test_previous_content_parsed_correctly(self):
        """previous_content dict must be parsed into sections/subsections maps."""
        svc = self._make_service()

        section_row = {"id": "sec-001", "title": "Results", "description": "Results section"}
        previous_content = {
            "sections": {"sec-intro": "Introduction content"},
            "subsections": {"sub-1": "Subsection 1 content"},
        }

        with patch("app.services.review_generation.main._get_supabase") as mock_sb:
            mock_client = mock_sb.return_value

            def table_handler(table_name):
                mock_q = MagicMock()
                if table_name == "structures":
                    single_resp = MagicMock()
                    single_resp.data = section_row
                    multi_resp = MagicMock()
                    multi_resp.data = []
                    mock_q.select.return_value.eq.return_value.single.return_value.execute.return_value = single_resp
                    mock_q.select.return_value.eq.return_value.execute.return_value = multi_resp
                elif table_name == "papers":
                    resp = MagicMock()
                    resp.data = []
                    mock_q.select.return_value.eq.return_value.eq.return_value.execute.return_value = resp
                elif table_name == "labels":
                    resp = MagicMock()
                    resp.data = []
                    mock_q.select.return_value.eq.return_value.execute.return_value = resp
                return mock_q

            mock_client.table.side_effect = table_handler

            context = await svc._build_section_context("rev-1", "sec-001", previous_content=previous_content)

        assert context.previous_sections_content == {"sec-intro": "Introduction content"}
        assert context.previous_subsections_content == {"sub-1": "Subsection 1 content"}
