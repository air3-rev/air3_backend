# app/services/data_extraction/refine.py
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, TypedDict, cast

from langchain.chains import LLMChain
from langchain.chains.combine_documents.refine import RefineDocumentsChain
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

from app.config import settings
from app.services.data_ingestion.types import Chunk
from app.services.data_extraction.prompts import _REFINE_PROMPT_TMPL, _INITIAL_PROMPT_TMPL, FORMAT_INSTRUCTIONS

logger = logging.getLogger(__name__)

# ---------- Schema & Parser ----------

class RefinedDoc(TypedDict, total=False):
    """Final structured payload produced by the refine chain."""
    summary: str
    key_points: List[str]
    extracted_items: List[Dict[str, Any]]
    sources: List[Dict[str, Any]]


def _llm() -> ChatOpenAI:
    base = ChatOpenAI(
        api_key=settings.openai_api_key,
        model="gpt-4o-mini",
        temperature=0.0,
        max_tokens=900,
        timeout=60,
    )
    # Ask for structured JSON (supported by recent OpenAI chat models)
    return base.bind(response_format={"type": "json_object"})

def _format_page_content(chunk: Chunk) -> str:
    """Serialize a Chunk into a stable, parseable page_content string."""
    cid = str(chunk.get("id", "")).strip()
    content = str(chunk.get("text", "")).strip()
    metadata = chunk.get("metadata", {}) or {}
    try:
        meta_json = json.dumps(metadata, ensure_ascii=False)
    except Exception:
        meta_json = "{}"
    sim = chunk.get("similarity", None)
    sim_str = f"{float(sim):.6f}" if isinstance(sim, (int, float)) else ""

    return (
        f"CHUNK_ID: {cid}\n"
        f"SIMILARITY: {sim_str}\n"
        "CONTENT:\n"
        f"{content}\n\n"
        "METADATA_JSON:\n"
        f"{meta_json}\n"
    )


def _chunks_to_documents(chunks: List[Chunk]) -> List[Document]:
    """Convert chunks to LangChain Documents used by the refine chain."""
    docs: List[Document] = []
    for c in chunks:
        page = _format_page_content(c)
        # Keep minimal metadata; page_content already embeds what we need.
        docs.append(Document(page_content=page, metadata={"id": c.get("id", "")}))
    return docs


def _json_loads_strict(text: str) -> RefinedDoc:
    """Strict JSON parsing with clear logging."""
    try:
        data = cast(RefinedDoc, json.loads(text))
        return data
    except Exception as e:
        logger.error("Refine chain returned non-JSON or invalid JSON. First 400 chars: %s", text[:400], exc_info=e)
        raise


def _dedup_list_of_str(items: Optional[List[str]]) -> List[str]:
    if not items:
        return []
    seen = set()
    out: List[str] = []
    for s in items:
        s_norm = " ".join(str(s).split())
        key = s_norm.lower()
        if s_norm and key not in seen:
            seen.add(key)
            out.append(s_norm)
    return out


def _dedup_sources(sources: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    if not sources:
        return []
    seen = set()
    out: List[Dict[str, Any]] = []
    for s in sources:
        cid = str(s.get("id", "")).strip()
        if cid and cid.lower() not in seen:
            seen.add(cid.lower())
            out.append({"id": cid, "reason": s.get("reason", "")})
    return out


def refine_relevant_chunks(chunks: List[Chunk]) -> Dict[str, Any]:
    """
    Use LangChain's RefineDocumentsChain to iteratively combine top-k chunks
    into a single structured JSON document.

    Args:
        chunks: List of retrieved chunks (id, text, metadata, similarity).

    Returns:
        Dict[str, Any] with keys: summary, key_points, extracted_items, sources.
    """
    if not chunks:
        logger.info("refine_relevant_chunks: empty input.")
        return {"summary": "", "key_points": [], "extracted_items": [], "sources": []}

    llm = _llm()

    # Prompts & chains
    document_prompt = PromptTemplate(
        input_variables=["page_content"],
        template="{page_content}",
    )
    document_variable_name = "context"
    initial_response_name = "prev_response"

    initial_prompt = PromptTemplate.from_template(_INITIAL_PROMPT_TMPL).partial(
        format_instructions=FORMAT_INSTRUCTIONS
    )
    refine_prompt = PromptTemplate.from_template(_REFINE_PROMPT_TMPL).partial(
        format_instructions=FORMAT_INSTRUCTIONS
    )

    initial_llm_chain = LLMChain(llm=llm, prompt=initial_prompt)
    refine_llm_chain = LLMChain(llm=llm, prompt=refine_prompt)

    chain = RefineDocumentsChain(
        initial_llm_chain=initial_llm_chain,
        refine_llm_chain=refine_llm_chain,
        document_prompt=document_prompt,
        document_variable_name=document_variable_name,
        initial_response_name=initial_response_name,
        return_intermediate_steps=False,
        verbose=False,
    )

    # Prepare docs and run the refine algorithm
    docs = _chunks_to_documents(chunks)

    # RefineDocumentsChain implements Runnable; invoke(docs) -> str (or dict in older LC).
    result = chain.invoke(docs)
    if isinstance(result, dict):
        # Older versions may return {"output_text": "..."}
        output_text = cast(str, result.get("output_text", "")) or cast(str, result.get("text", "")) or ""
    else:
        output_text = cast(str, result)

    refined: RefinedDoc = _json_loads_strict(output_text)

    # Final sanity/cleanup
    refined.setdefault("summary", "")
    refined.setdefault("key_points", [])
    refined.setdefault("extracted_items", [])
    refined.setdefault("sources", [])

    refined["key_points"] = _dedup_list_of_str(refined["key_points"])[:15]  # type: ignore[index]
    refined["sources"] = _dedup_sources(refined["sources"])  # type: ignore[assignment]

    return dict(refined)
