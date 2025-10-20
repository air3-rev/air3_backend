"""Literature review generation service using LangChain."""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

from app.services.data_extraction.fetch import _get_supabase
from app.schemas.review_generation import (
    GenerateSectionRequest,
    GenerateSectionResponse,
    SectionContext,
    SubsectionContext,
    SectionData,
    PaperExtractedData
)

logger = logging.getLogger(__name__)


class ReviewGenerationService:
    """Service for generating literature review content using LangChain."""

    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.3,  # Lower temperature for more consistent academic writing
            max_tokens=2000
        )

    async def generate_section_content(self, request: GenerateSectionRequest) -> GenerateSectionResponse:
        """
        Generate content for a section or subsection of the literature review.

        Args:
            request: Generation request with review_id, section_id, and optional subsection_id

        Returns:
            GenerateSectionResponse with the generated content
        """
        try:
            # Build context for generation
            if request.subsection_id:
                context = await self._build_subsection_context(
                    request.review_id,
                    request.section_id,
                    request.subsection_id,
                    request.previous_content
                )
                content = await self._generate_subsection_content(context)
            else:
                context = await self._build_section_context(
                    request.review_id,
                    request.section_id,
                    request.previous_content
                )
                content = await self._generate_section_content(context)

            return GenerateSectionResponse(
                content=content,
                section_id=request.section_id,
                subsection_id=request.subsection_id,
                metadata={
                    "context_used": True,
                    "papers_count": len(context.assigned_papers) if hasattr(context, 'assigned_papers') else 0
                }
            )

        except Exception as e:
            logger.exception(f"Error generating content for section {request.section_id}")
            raise

    async def _build_section_context(
        self,
        review_id: str,
        section_id: str,
        previous_content: Optional[Dict[str, Any]] = None
    ) -> SectionContext:
        """Build context information needed for section generation."""
        sb = _get_supabase()

        # Get section details
        section_data = sb.table('structures').select('id, title, description').eq('id', section_id).single().execute()
        if not section_data.data:
            raise ValueError(f"Section {section_id} not found")

        # Get subsections for this section
        subsections_result = sb.table('structures').select('id, title, description').eq('parent_id', section_id).execute()
        subsections = [
            {"id": sub["id"], "title": sub["title"], "description": sub["description"]}
            for sub in subsections_result.data or []
        ]

        section = SectionData(
            id=section_data.data["id"],
            title=section_data.data["title"],
            description=section_data.data["description"],
            subsections=subsections
        )

        # Get papers assigned to this section
        papers_result = sb.table('papers').select('id').eq('section_id', section_id).eq('review_id', review_id).execute()
        assigned_papers = [paper["id"] for paper in papers_result.data or []]

        # Get extracted data for assigned papers
        extracted_data = []
        if assigned_papers:
            # Get all labels for this review
            labels_result = sb.table('labels').select('id, name').eq('review_id', review_id).execute()
            label_ids = [label["id"] for label in labels_result.data or []]

            if label_ids:
                # Get extracted data for these papers and labels
                data_result = sb.table('extracted_data').select('paper_id, label_id, data').in_('paper_id', assigned_papers).in_('label_id', label_ids).execute()

                # Enrich with label names
                label_map = {label["id"]: label["name"] for label in labels_result.data or []}
                for item in data_result.data or []:
                    extracted_data.append(PaperExtractedData(
                        paper_id=item["paper_id"],
                        label_name=label_map.get(item["label_id"], "Unknown"),
                        data=item["data"],
                        created_at=datetime.now()  # We don't have this in the query, but it's not critical
                    ))

        # Build previous content context
        previous_sections_content = {}
        previous_subsections_content = {}
        if previous_content:
            previous_sections_content = previous_content.get("sections", {})
            previous_subsections_content = previous_content.get("subsections", {})

        return SectionContext(
            section=section,
            assigned_papers=assigned_papers,
            extracted_data=extracted_data,
            previous_sections_content=previous_sections_content,
            previous_subsections_content=previous_subsections_content
        )

    async def _build_subsection_context(
        self,
        review_id: str,
        section_id: str,
        subsection_id: str,
        previous_content: Optional[Dict[str, Any]] = None
    ) -> SubsectionContext:
        """Build context information needed for subsection generation."""
        sb = _get_supabase()

        # Get section details
        section_data = sb.table('structures').select('id, title, description').eq('id', section_id).single().execute()
        if not section_data.data:
            raise ValueError(f"Section {section_id} not found")

        # Get subsection details
        subsection_data = sb.table('structures').select('id, title, description').eq('id', subsection_id).single().execute()
        if not subsection_data.data:
            raise ValueError(f"Subsection {subsection_id} not found")

        subsection = {
            "id": subsection_data.data["id"],
            "title": subsection_data.data["title"],
            "description": subsection_data.data["description"]
        }

        # Get all subsections for this section to determine order
        all_subsections = sb.table('structures').select('id, title, description').eq('parent_id', section_id).order('display_order').execute()
        subsections = [
            {"id": sub["id"], "title": sub["title"], "description": sub["description"]}
            for sub in all_subsections.data or []
        ]

        section = SectionData(
            id=section_data.data["id"],
            title=section_data.data["title"],
            description=section_data.data["description"],
            subsections=subsections
        )

        # Get papers assigned to this section
        papers_result = sb.table('papers').select('id').eq('section_id', section_id).eq('review_id', review_id).execute()
        assigned_papers = [paper["id"] for paper in papers_result.data or []]

        # Get extracted data (same as section context)
        extracted_data = []
        if assigned_papers:
            labels_result = sb.table('labels').select('id, name').eq('review_id', review_id).execute()
            label_ids = [label["id"] for label in labels_result.data or []]

            if label_ids:
                data_result = sb.table('extracted_data').select('paper_id, label_id, data').in_('paper_id', assigned_papers).in_('label_id', label_ids).execute()

                label_map = {label["id"]: label["name"] for label in labels_result.data or []}
                for item in data_result.data or []:
                    extracted_data.append(PaperExtractedData(
                        paper_id=item["paper_id"],
                        label_name=label_map.get(item["label_id"], "Unknown"),
                        data=item["data"],
                        created_at=datetime.now()
                    ))

        # Build previous content context
        section_content = ""
        previous_subsections_content = {}
        if previous_content:
            section_content = previous_content.get("section_content", "")
            previous_subsections_content = previous_content.get("previous_subsections", {})

        return SubsectionContext(
            section=section,
            subsection=subsection,
            assigned_papers=assigned_papers,
            extracted_data=extracted_data,
            section_content=section_content,
            previous_subsections_content=previous_subsections_content
        )

    async def _generate_section_content(self, context: SectionContext) -> str:
        """Generate content for a section using LangChain."""
        # Prepare extracted data summary
        data_summary = self._prepare_extracted_data_summary(context.extracted_data)

        # Prepare previous content context
        previous_context = ""
        if context.previous_sections_content:
            previous_sections = list(context.previous_sections_content.values())
            if previous_sections:
                previous_context = "\n\n".join(previous_sections[-2:])  # Include last 2 sections for context

        # Create prompt
        prompt = PromptTemplate(
            input_variables=["section_title", "section_description", "data_summary", "previous_context", "subsections"],
            template="""You are an expert academic writer creating a literature review section.

SECTION TO WRITE:
Title: {section_title}
Description: {section_description}

EXTRACTED DATA FROM ASSIGNED PAPERS:
{data_summary}

PREVIOUS SECTIONS CONTEXT:
{previous_context}

SUBSECTIONS TO BE WRITTEN:
{subsections}

INSTRUCTIONS:
- Write a coherent, academic section that synthesizes the extracted data from the assigned papers
- Focus ONLY on papers that have been assigned to this section
- Maintain academic tone and proper citations (use paper IDs as placeholders)
- Consider the context from previous sections but don't repeat information
- Keep the section focused on its specific scope and description
- Write in a narrative style that flows naturally
- Aim for 300-600 words
- End the section in a way that leads naturally into the subsections

Write the section content:"""
        )

        chain = LLMChain(llm=self.llm, prompt=prompt)

        subsections_text = "\n".join([f"- {sub['title']}: {sub['description']}" for sub in context.section.subsections])

        result = await chain.arun(
            section_title=context.section.title,
            section_description=context.section.description,
            data_summary=data_summary,
            previous_context=previous_context,
            subsections=subsections_text
        )

        return result.strip()

    async def _generate_subsection_content(self, context: SubsectionContext) -> str:
        """Generate content for a subsection using LangChain."""
        # Prepare extracted data summary
        data_summary = self._prepare_extracted_data_summary(context.extracted_data)

        # Prepare previous content context
        previous_context = ""
        if context.previous_subsections_content:
            previous_subs = list(context.previous_subsections_content.values())
            if previous_subs:
                previous_context = "\n\n".join(previous_subs[-1:])  # Include last subsection for context

        # Create prompt
        prompt = PromptTemplate(
            input_variables=["section_title", "subsection_title", "subsection_description", "section_content", "data_summary", "previous_context"],
            template="""You are an expert academic writer creating a subsection of a literature review.

PARENT SECTION: {section_title}
SECTION CONTENT SO FAR: {section_content}

SUBSECTION TO WRITE:
Title: {subsection_title}
Description: {subsection_description}

EXTRACTED DATA FROM ASSIGNED PAPERS:
{data_summary}

PREVIOUS SUBSECTIONS CONTEXT:
{previous_context}

INSTRUCTIONS:
- Write a focused subsection that addresses the specific aspect described
- Use the extracted data from assigned papers to support your points
- Maintain consistency with the parent section's content and tone
- Consider what has been written in previous subsections to avoid repetition
- Focus on the specific scope of this subsection
- Write in academic style with proper citations (use paper IDs as placeholders)
- Aim for 200-400 words
- Ensure smooth integration with the overall section narrative

Write the subsection content:"""
        )

        chain = LLMChain(llm=self.llm, prompt=prompt)

        result = await chain.arun(
            section_title=context.section.title,
            subsection_title=context.subsection["title"],
            subsection_description=context.subsection["description"],
            section_content=context.section_content,
            data_summary=data_summary,
            previous_context=previous_context
        )

        return result.strip()

    def _prepare_extracted_data_summary(self, extracted_data: List[PaperExtractedData]) -> str:
        """Prepare a summarized version of extracted data for the LLM prompt."""
        if not extracted_data:
            return "No extracted data available for assigned papers."

        # Group by label
        label_groups = {}
        for item in extracted_data:
            label = item.label_name
            if label not in label_groups:
                label_groups[label] = []
            label_groups[label].append(f"Paper {item.paper_id}: {item.data}")

        # Format as readable text
        summary_parts = []
        for label, papers_data in label_groups.items():
            summary_parts.append(f"{label}:")
            for paper_data in papers_data[:5]:  # Limit to 5 papers per label to avoid token limits
                summary_parts.append(f"  - {paper_data}")
            if len(papers_data) > 5:
                summary_parts.append(f"  - ... and {len(papers_data) - 5} more papers")

        return "\n".join(summary_parts)


# Global service instance
review_generation_service = ReviewGenerationService()