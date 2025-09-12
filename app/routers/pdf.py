import fitz  # PyMuPDF
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import re
import math
from collections import defaultdict

router = APIRouter()

class ExtractedMeta(BaseModel):
    title: str
    abstract: str
    authors: List[str]
    journal: str

@router.post("/extract-pdf-metadata", response_model=ExtractedMeta)
async def extract_pdf_metadata(file: UploadFile = File(...)) -> ExtractedMeta:
    """
    Extract metadata from first page with font-size-based title detection.
    If the largest line is a journal header/masthead, it chooses the next-largest valid line.
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        # Read the uploaded file
        file_content = await file.read()
        
        # Use PyMuPDF for text extraction with positioning
        doc = fitz.open(stream=file_content, filetype="pdf")
        page = doc[0]  # First page
        
        # Get page dimensions
        page_rect = page.rect
        page_height = page_rect.height
        page_width = page_rect.width
        
        # Extract text with detailed information using get_text("dict")
        text_dict = page.get_text("dict")
        
        # Helper functions (matching original TypeScript)
        def get_y(transform):
            return transform[5] if len(transform) > 5 else 0  # translateY (origin bottom)
        
        def get_x(transform):
            return transform[4] if len(transform) > 4 else 0  # translateX
        
        def get_font_size(span):
            return span.get("size", 0)
        
        # Extract items from PDF
        items = []
        for block in text_dict.get("blocks", []):
            if "lines" in block:
                for line in block["lines"]:
                    for span in line["spans"]:
                        text = span.get("text", "").strip()
                        if text:
                            bbox = span.get("bbox", [0, 0, 0, 0])
                            items.append({
                                "str": text,
                                "transform": [0, 0, 0, 0, bbox[0], page_height - bbox[1]],  # Convert to bottom-origin
                                "height": span.get("size", 0)
                            })
        
        doc.close()
        
        if not items:
            raise Exception("No text items found")
        
        # Group into lines (matching original logic)
        LINE_Y_TOL = 4
        buckets = defaultdict(list)
        
        for item in items:
            y = get_y(item["transform"])
            key = round(y / LINE_Y_TOL) * LINE_Y_TOL
            buckets[key].append(item)
        
        lines = []
        for y, item_list in buckets.items():
            # Sort by x position
            sorted_items = sorted(item_list, key=lambda i: get_x(i["transform"]))
            text = ' '.join(item["str"] for item in sorted_items)
            text = re.sub(r'\s+', ' ', text.strip())
            
            if len(text) >= 2:
                font_sizes = [get_font_size({"size": item.get("height", 0)}) for item in sorted_items if item.get("height", 0) > 0]
                max_font = max(font_sizes) if font_sizes else 0
                avg_font = sum(font_sizes) / len(font_sizes) if font_sizes else 0
                x_positions = [get_x(item["transform"]) for item in sorted_items]
                x_min = min(x_positions)
                x_max = max(x_positions)
                center_x = (x_min + x_max) / 2
                
                lines.append({
                    "y": y,
                    "text": text,
                    "maxFont": max_font,
                    "avgFont": avg_font,
                    "xMin": x_min,
                    "xMax": x_max,
                    "centerX": center_x
                })
        
        # Text in reading order (top to bottom)
        lines_top_to_bottom = sorted(lines, key=lambda l: -l["y"])
        text_by_lines = '\n'.join(line["text"] for line in lines_top_to_bottom)
        page_text = ' '.join(item["str"] for item in items)
        page_text = re.sub(r'\s+', ' ', page_text.strip())
        
        # Consider only top portion for journal/title detection
        TOP_PORTION = 0.65
        y_threshold = page_height * (1 - TOP_PORTION)
        top_lines = [line for line in lines if line["y"] >= y_threshold]
        
        # Cluster by font size (quantize to reduce tiny differences)
        def bin_font_size(font_size):
            return round(font_size)
        
        by_bin = defaultdict(list)
        for line in top_lines:
            bin_size = bin_font_size(line["maxFont"])
            by_bin[bin_size].append(line)
        
        # Rank bins by size (largest first)
        bins_desc = sorted(by_bin.keys(), reverse=True)
        
        def join_bin_lines(bin_size):
            """Build phrase from lines in same bin by joining adjacent lines"""
            group = by_bin[bin_size]
            # Sort top->bottom
            sorted_group = sorted(group, key=lambda l: -l["y"])
            
            # Merge adjacent lines
            JOIN_Y_TOL = max(10, (bin_size or 10) * 1.6)
            CENTER_PREF = page_width * 0.35
            blocks = []
            
            for line in sorted_group:
                if blocks and abs(blocks[-1][-1]["y"] - line["y"]) <= JOIN_Y_TOL:
                    blocks[-1].append(line)
                else:
                    blocks.append([line])
            
            # Pick block with best heuristic score
            scored_blocks = []
            for block in blocks:
                text = ' '.join(l["text"] for l in block)
                text = re.sub(r'\s+', ' ', text.strip())
                center_x = sum(l["centerX"] for l in block) / len(block)
                dist_center = abs(center_x - page_width / 2)
                score = len(text) - dist_center / CENTER_PREF
                scored_blocks.append((text, score))
            
            scored_blocks.sort(key=lambda x: -x[1])
            return scored_blocks[0][0] if scored_blocks else ""
        
        # Pick journal (largest bin) & title (second largest bin)
        journal = ""
        title = ""
        
        if len(bins_desc) >= 1:
            journal = join_bin_lines(bins_desc[0])
        if len(bins_desc) >= 2:
            title = join_bin_lines(bins_desc[1])
        
        # Clean obvious cruft
        def clean_text(text):
            text = re.sub(r'\s*©\s*\d{4}.*', '', text, flags=re.IGNORECASE)
            text = re.sub(r'\s*All rights reserved.*', '', text, flags=re.IGNORECASE)
            text = re.sub(r'\s*DOI:.*', '', text, flags=re.IGNORECASE)
            text = re.sub(r'\s*www\.[^\s]+', '', text, flags=re.IGNORECASE)
            return text.strip()
        
        journal = clean_text(journal)
        title = clean_text(title)
        
        # Fallbacks if clusters are empty or too short
        if not journal or len(journal) < 3:
            # Try absolute largest line in top portion
            if top_lines:
                max_line = max(top_lines, key=lambda l: l["maxFont"])
                journal = clean_text(max_line["text"])
        
        if not title or len(title) < 5:
            # Choose next largest non-empty line not identical to journal
            sorted_top_lines = sorted(top_lines, key=lambda l: (-l["maxFont"], -l["y"]))
            for line in sorted_top_lines:
                clean_line_text = clean_text(line["text"])
                if clean_line_text and clean_line_text != journal:
                    title = clean_line_text
                    break
            
            if not title:
                title = file.filename.replace('.pdf', '') if file.filename else 'Unknown Title'
        
        # Extract abstract (fixed regex patterns)
        abstract_pattern = r'abstract[\s:\-]*(.*?)(?=\n\s*(?:introduction|keywords|methods|results|background|1\.|I\.|references)\b)'
        abstract_match = re.search(abstract_pattern, text_by_lines, re.IGNORECASE | re.DOTALL)
        if not abstract_match:
            abstract_match = re.search(abstract_pattern, page_text, re.IGNORECASE | re.DOTALL)
        
        abstract = ""
        if abstract_match:
            abstract = re.sub(r'\s+', ' ', abstract_match.group(1)).strip()
        
        # Extract authors
        title_idx = text_by_lines.find(title) if title else -1
        authors_block = ""
        
        if title_idx >= 0:
            next_section_regex = r'(?:\nabstract\b|\nintroduction\b|\nbackground\b|\nmethods\b)'
            remaining_text = text_by_lines[title_idx + len(title):]
            next_match = re.search(next_section_regex, remaining_text, re.IGNORECASE)
            
            if next_match:
                authors_block = remaining_text[:next_match.start()]
            else:
                authors_block = ' '.join(remaining_text.split('\n')[:3])
        
        authors = []
        if authors_block:
            author_candidates = re.split(r'[,\n;]+', authors_block)
            for author in author_candidates:
                author = author.strip()
                exclude_terms = ['abstract', 'keywords', 'university', 'department', 
                               'doi:', 'http', '©', '@', 'orcid']
                if (author and 
                    not any(term in author.lower() for term in exclude_terms)):
                    authors.append(author)
        
        return ExtractedMeta(
            title=title,
            abstract=abstract,
            authors=authors,
            journal=journal
        )
        
    except Exception as error:
        print(f"Error extracting PDF metadata: {error}")
        return ExtractedMeta(
            title=file.filename.replace('.pdf', '') if file.filename else 'Unknown Title',
            abstract='Failed to extract abstract',
            authors=[],
            journal=''
        )

@router.post("/debug-pdf-text")
async def debug_pdf_text(file: UploadFile = File(...)):
    """Debug endpoint to see what text is extracted from PDF"""
    try:
        file_content = await file.read()
        doc = fitz.open(stream=file_content, filetype="pdf")
        page = doc[0]
        
        simple_text = page.get_text()
        doc.close()
        
        return {
            "simple_text": simple_text[:1000],
            "simple_text_lines": simple_text.split('\n')[:20],
            "has_text": bool(simple_text.strip())
        }
    except Exception as e:
        return {"error": str(e)}