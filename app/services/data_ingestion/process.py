import logging
from typing import List

from app.constants import CHUNK_SIZE
import tiktoken
from langchain_core.documents import Document

# from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.services.data_ingestion.types import PdfDocument

logger = logging.getLogger(__name__)


CHUNK_OVERLAP = 200
# EMBED_MODEL = "text-embedding-3-large"  # 3072-d
# embeddings_model = OpenAIEmbeddings(model=EMBED_MODEL)


def _tiktoken_len(text: str) -> int:
    enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


def chunk_document(pdf_doc: PdfDocument) -> List[Document]:
    """
    Split the PDF text into token-aware, overlapping chunks and return
    LangChain Documents (ready for SupabaseVectorStore.add_documents).
    """
    if not getattr(pdf_doc, "content", None) or not pdf_doc.content.strip():
        logger.warning("Empty PdfDocument passed to chunk_document")
        return []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=_tiktoken_len,  # token-aware
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    raw_chunks = splitter.split_text(pdf_doc.content)
    docs: List[Document] = []
    for idx, chunk in enumerate(raw_chunks):
        docs.append(
            Document(
                page_content=chunk,
                metadata={
                    "doc_id": pdf_doc.doc_id,
                    "chunk_index": idx,
                    "filename": pdf_doc.file_name,
                    "page_count": pdf_doc.num_pages,
                },
            )
        )

    # logger.info(
    #     "Chunked document %s into %d chunks",
    #     getattr(pdf_doc, "doc_id", "unknown"),
    #     len(docs),
    # )
    return docs


# def embed_chunks(docs: List[Document]) -> List[List[float]]:
#     """
#     Embed chunks in one call (LangChain handles its own batching internally).
#     Use this only if you plan to call SupabaseVectorStore.add_vectors(...).
#     If you’ll use add_documents(...), you can skip explicit embedding.
#     """
#     if not docs:
#         logger.warning("No documents provided to embed_chunks")
#         return []

#     texts = [d.page_content for d in docs]
#     vectors = embeddings_model.embed_documents(texts)  # single call, no manual loop
#     logger.info("Embedded %d chunks", len(vectors))
#     return vectors
