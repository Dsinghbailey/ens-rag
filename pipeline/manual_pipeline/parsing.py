import logging
import re
import requests
from typing import List, Dict, Any

# Use markdown-it-py for parsing
from markdown_it import MarkdownIt

# Import config variables needed for AI metadata
from .config import OPENAI_API_KEY, OPENAI_LLM_MODEL, MAX_CHUNK_TOKENS, OVERLAP_SENTENCES, OPENAI_API_URL

# --- Parsing, Chunking & Metadata ---

md = MarkdownIt(
    "commonmark", {"breaks": False, "html": False}
)  # Configure parser as needed


def chunk_markdown_with_overlap(
    markdown_text: str, source_identifier: str
) -> List[Dict[str, Any]]:
    """
    Structure-aware chunking for Markdown with sentence overlap.
    Placeholder: Improves the very basic heading/size splitting.
    NOTE: This is still rudimentary. A production system would likely use
    markdown-it-py's token stream or an AST for more robust structure detection
    (paragraphs, code blocks, lists, tables) and smarter splitting logic.
    """
    logging.info(f"Chunking {source_identifier}...")
    chunks_with_metadata = []
    lines = markdown_text.splitlines()
    current_chunk_lines = []
    current_headings = {}
    last_chunk_text = ""  # For overlap calculation

    # Use simple character count as a proxy for tokens (replace with tiktoken if needed)
    # Target ~MAX_CHUNK_TOKENS * 4 chars as a rough estimate
    APPROX_CHAR_LIMIT = MAX_CHUNK_TOKENS * 4

    def finalize_chunk(force=False):
        nonlocal current_chunk_lines, last_chunk_text, chunks_with_metadata, current_headings
        current_chunk_text = "\n".join(current_chunk_lines).strip()
        if not current_chunk_text:
            return

        # Check size before adding overlap
        if force or len(current_chunk_text) > APPROX_CHAR_LIMIT * 0.6: # Only finalize if reasonably sized or forced
            overlap_text = ""
            if OVERLAP_SENTENCES > 0 and last_chunk_text:
                # Crude sentence split (use nltk.sent_tokenize for better results)
                sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?|!)(\s|\n)(?=[A-Z])', last_chunk_text)
                valid_sentences = [s.strip() for s in sentences if s and s.strip()]
                if valid_sentences:
                    overlap_sentences = valid_sentences[-OVERLAP_SENTENCES:]
                    overlap_text = " ".join(overlap_sentences).strip()
                    # Ensure overlap doesn't make chunk too big
                    if len(overlap_text) + len(current_chunk_text) > APPROX_CHAR_LIMIT * 1.5:
                        logging.warning(f"Overlap skipped for chunk in {source_identifier} due to size limit.")
                        overlap_text = ""
                    elif overlap_text:
                       # Add sentence terminator if missing
                       if overlap_text[-1] not in ('.', '?', '!'):
                            overlap_text += ". " # Add period if structure is paragraph like
                       else:
                           overlap_text += " "

            final_text = overlap_text + current_chunk_text

            # Further split if the chunk is still too large
            if len(final_text) > APPROX_CHAR_LIMIT * 1.2:
                logging.warning(f"Chunk longer than limit ({len(final_text)} chars) in {source_identifier}, attempting simple split.")
                # Simple midpoint split (can break code blocks/logic)
                mid = len(final_text) // 2
                # Find a sentence break near the middle
                split_point = mid + final_text[mid:].find('.') + 1
                if split_point <= mid:
                     split_point = mid + final_text[mid:].find('\n') + 1
                if split_point <= mid:
                     split_point = mid # Fallback to hard split

                chunk1_text = final_text[:split_point].strip()
                chunk2_text = final_text[split_point:].strip()
                if chunk1_text:
                     chunks_with_metadata.append({
                        "text": chunk1_text,
                        "metadata_raw": {
                            "source_identifier": source_identifier,
                            "headings": current_headings.copy(),
                         }
                    })
                if chunk2_text:
                    chunks_with_metadata.append({
                        "text": chunk2_text,
                        "metadata_raw": {
                             "source_identifier": source_identifier,
                             "headings": current_headings.copy(), # Keep same headings for split part
                         }
                     })
                last_chunk_text = chunk2_text # Use second part for next overlap

            else:
                 chunks_with_metadata.append({
                     "text": final_text,
                     "metadata_raw": {
                         "source_identifier": source_identifier,
                         "headings": current_headings.copy(),
                     }
                 })
                 last_chunk_text = final_text # Use the whole text for next overlap

            current_chunk_lines = [] # Reset lines for the next chunk

    for line in lines:
        is_heading = False
        if line.startswith("### "):
            # Split before adding H3 if current chunk has content
            finalize_chunk()
            current_headings["h3"] = line[4:].strip()
            # Clear lower headings if any were set
            current_headings.pop("h4", None)
            current_headings.pop("h5", None)
            current_headings.pop("h6", None)
            is_heading = True
        elif line.startswith("## "):
            finalize_chunk()
            current_headings = {
                "h1": current_headings.get("h1"),
                "h2": line[3:].strip(),
            }
            is_heading = True
        elif line.startswith("# "):
            finalize_chunk()
            current_headings = {"h1": line[2:].strip()}
            is_heading = True

        current_chunk_lines.append(line)

        # Check size after adding line (crude check)
        current_length = sum(len(l) + 1 for l in current_chunk_lines)
        if not is_heading and current_length > APPROX_CHAR_LIMIT:
             # Don't split mid-code block ideally (needs better detection)
             if not ('```' in current_chunk_lines[-1] or (len(current_chunk_lines)>1 and '```' in current_chunk_lines[-2])):
                finalize_chunk()
                # If the line itself was huge, add it back to start the next chunk
                if len(line) > APPROX_CHAR_LIMIT:
                    logging.warning(f"Single line exceeds character limit in {source_identifier}")
                    current_chunk_lines.append(line)
                    finalize_chunk(force=True) # Force finalize this huge line as its own chunk
                elif line.strip(): # Add non-empty line back to start next chunk if it wasn't the cause of the split
                     current_chunk_lines.append(line)


    # Add the last remaining chunk
    finalize_chunk(force=True)

    logging.info(
        f"Generated {len(chunks_with_metadata)} raw chunks for {source_identifier}."
    )

    # --- Post-process chunks to add final metadata ---
    processed_chunks = []
    for chunk_info in chunks_with_metadata:
        if not chunk_info["text"]:
            continue
        metadata = extract_basic_metadata(
            chunk_info["text"], chunk_info["metadata_raw"]
        )
        # --- Optional: Add AI Metadata ---
        # Uncomment if needed, but be mindful of cost/latency
        # try:
        #     ai_meta = extract_ai_metadata(chunk_info["text"])
        #     metadata.update(ai_meta)
        # except Exception as e:
        #     logging.warning(f"Failed to get AI metadata for chunk in {source_identifier}: {e}")
        # --- End Optional AI ---
        processed_chunks.append({"text": chunk_info["text"], "metadata": metadata})
    return processed_chunks


def extract_basic_metadata(chunk_text: str, raw_meta: Dict) -> Dict:
    """Extracts V1 metadata: source, headings, chunk type guess, code lang, keywords."""
    metadata = {
        "source_url": raw_meta.get("source_identifier", ""),
        "parent_headings": raw_meta.get("headings", {}),
        "chunk_type": "text",  # Default
        "code_language": None,
        "keywords": [],
        # "eip_numbers": [] # Explicit field for EIPs
    }

    # Guess chunk type (very basic - improve with parser info)
    lines = chunk_text.strip().split('\n')
    if lines:
        first_line = lines[0].strip()
        if first_line.startswith("```") and len(lines) > 1 and lines[-1].strip() == "```":
            metadata["chunk_type"] = "code_block"
            try:
                lang = first_line[3:].strip()
                if lang:
                    metadata["code_language"] = lang.lower()
            except:
                pass  # Ignore errors in simple parsing
        elif first_line.startswith("* ") or first_line.startswith("- ") or re.match(r"^\d+\. ", first_line):
            # Check if most lines start similarly (indicative of a list)
            list_markers = sum(1 for line in lines if line.strip().startswith("* ") or line.strip().startswith("- ") or re.match(r"^\d+\. ", line.strip()))
            if list_markers / len(lines) > 0.6:
                metadata["chunk_type"] = (
                    "list_item_group"
                )
        elif first_line.startswith("#"):
             # Check if it's *only* a heading line
             if len(lines) == 1:
                 metadata["chunk_type"] = "heading"
        # Add table detection? (e.g., presence of |---|)
        elif any("|---" in line for line in lines):
             metadata["chunk_type"] = "table"

    # Simple Keyword Extraction (placeholder - use regex/better NLP)
    # Extract alphanumeric words, longer than 3 chars, avoiding pure numbers
    words = re.findall(r'\b[a-zA-Z][a-zA-Z0-9_]{3,}\b', chunk_text)
    # Simple frequency count
    word_counts = {}
    for word in words:
        lw = word.lower()
        word_counts[lw] = word_counts.get(lw, 0) + 1
    # Get top N keywords based on frequency (and ignore common words maybe?)
    # TODO: Add stop word filtering
    sorted_words = sorted(word_counts.items(), key=lambda item: item[1], reverse=True)
    metadata["keywords"] = [word for word, count in sorted_words[:15]]

    # Add EIP numbers if found
    eips = re.findall(r'\bEIP-?(\d+)\b', chunk_text, re.IGNORECASE)
    if eips:
        eip_keywords = [f"EIP-{num}" for num in eips]
        # metadata["eip_numbers"] = sorted(list(set(int(num) for num in eips)))
        metadata["keywords"] = sorted(list(set(metadata["keywords"] + eip_keywords)))

    return metadata


def extract_ai_metadata(chunk_text: str) -> Dict:
    """Uses GPT-4o mini to extract summary or keywords."""
    # This is optional and adds cost/latency
    # Implement retry logic for production
    if not OPENAI_API_KEY or not OPENAI_API_URL:
        logging.warning("OpenAI API Key or URL not configured, skipping AI metadata.")
        return {}

    logging.info(
        f"Extracting AI metadata for chunk starting with: {chunk_text[:50].replace('\n', ' ')}..."
    )
    # Limit input size to avoid excessive cost/tokens
    max_input_chars = 3000 # Approx 750 tokens
    truncated_text = chunk_text[:max_input_chars]

    prompt = f"Analyze the following technical documentation chunk. Provide a concise one-sentence summary and list up to 5 key technical entities or concepts mentioned. Focus on specific nouns, technologies, or standards.\n\nCHUNK:\n{truncated_text}\n\nOUTPUT FORMAT (exactly two lines):\nSummary: [Your one-sentence summary]\nKeywords: [keyword1, keyword2, keyword3, keyword4, keyword5]"
    try:
        response = requests.post(
            OPENAI_API_URL,
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": OPENAI_LLM_MODEL,
                "messages": [{
                    "role": "system",
                    "content": "You are an expert technical documentation analyst."
                    },
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1,  # Very low temp for factual extraction
                "max_tokens": 150,
                "stop": ["\n\n"]
            },
            timeout=45,
        )
        response.raise_for_status()
        completion = response.json()
        content = (
            completion.get("choices", [{}])[0].get("message", {}).get("content", "")
        ).strip()

        # Improved parsing of the response based on the strict format
        summary_part = ""
        keywords_part = []
        lines = content.split('\n')
        if len(lines) >= 1 and lines[0].lower().startswith("summary:"):
            summary_part = lines[0][len("summary:"):].strip()
        if len(lines) >= 2 and lines[1].lower().startswith("keywords:"):
            keywords_str = lines[1][len("keywords:"):].strip()
            # Handle potential brackets and clean up
            keywords_str = keywords_str.strip("[]")
            keywords_part = [
                k.strip() for k in keywords_str.split(",") if k.strip()
            ]

        if summary_part or keywords_part:
            ai_meta = {}
            if summary_part:
                ai_meta["ai_summary"] = summary_part
            if keywords_part:
                ai_meta["ai_keywords"] = keywords_part
            return ai_meta
        else:
            logging.warning(f"Could not parse AI metadata from response: {content}")
            return {}

    except requests.exceptions.Timeout:
        logging.error(f"Timeout calling OpenAI API for metadata extraction.")
        return {}
    except requests.exceptions.RequestException as e:
        logging.error(f"Error calling OpenAI API: {e}")
        if hasattr(e, "response") and e.response is not None:
            logging.error(f"OpenAI Response Status: {e.response.status_code}, Body: {e.response.text}")
        return {}
    except Exception as e:
        logging.error(f"Error processing OpenAI response: {e}", exc_info=True)
        return {} 