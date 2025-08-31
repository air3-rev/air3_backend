
from __future__ import annotations

from typing import Any, List
from pydantic import BaseModel, Field
from langchain_core.output_parsers import JsonOutputParser

class ExtractedItem(BaseModel):
    name: str = Field(..., description="Normalized field name")
    value: Any = Field(..., description="Associated value")

class SourceItem(BaseModel):
    id: str
    reason: str = ""

class RefinedDocModel(BaseModel):
    summary: str = ""
    key_points: List[str] = []
    extracted_items: List[ExtractedItem] = []
    sources: List[SourceItem] = []

parser = JsonOutputParser(pydantic_object=RefinedDocModel)

FORMAT_INSTRUCTIONS = parser.get_format_instructions()  

_INITIAL_PROMPT_TMPL = """You are a precise data extractor.

You will read ONE context block (variable: {{context}}) and produce a compact JSON object.
Follow these format rules strictly:
{format_instructions}

Context you will receive contains:
CHUNK_ID, SIMILARITY, CONTENT, and METADATA_JSON.

Only include fields required by the format above.
Do NOT add commentary or prose outside JSON.

Context:
{context}
"""

_REFINE_PROMPT_TMPL = """You are refining an existing JSON doc using NEW context (variable: {{context}}).
Update only where the new context adds value or corrects errors. Keep the schema IDENTICAL.

Rules:
- Preserve prior good content; merge new details succinctly.
- De-duplicate aggressively.
- If contradictions exist, prefer NEW context.
- Append a new source for this chunk using its CHUNK_ID.

Follow these format rules strictly:
{format_instructions}

Current JSON:
{prev_response}

New context:
{context}
"""
