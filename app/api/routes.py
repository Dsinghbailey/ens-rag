from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import os
import re
import logging
from llama_index.embeddings.voyageai import VoyageEmbedding

from llama_index.core.chat_engine import SimpleChatEngine
from llama_index.llms.openai import OpenAI
from llama_index.core.types import ChatMessage, MessageRole
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.postprocessor import SimilarityPostprocessor
from llama_index.core.retrievers import BaseRetriever
from dotenv import load_dotenv
import time
import httpx

load_dotenv()
# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

router = APIRouter()

# --- Globals for initialization ---
# These will be set during application startup
query_retriever: Optional[BaseRetriever] = None
embedding_model: Optional[VoyageEmbedding] = None
# --- End Globals ---

# Constants
SYSTEM_PROMPT = """
**You are an friendly AI assistant answering questions strictly based on the provided ENS documentation sources ONLY.**
Your primary goal is accuracy based *solely* on the numbered sources below.

**CRITICAL RULES:**
1.  **DO NOT USE EXTERNAL KNOWLEDGE.** Base your entire answer *only* on the information directly derivable from the numbered sources provided in the 'SOURCES' section below. You may synthesize information by combining facts across different sources or sections of the provided context, but do not add information not present in the sources.
2.  **Handling Unanswerable Questions:**
    *   **If the question is about ENS but the answer *cannot* be reasonably assembled from the 'SOURCES' section:** Explain that the provided documentation does not contain the specific information requested. Suggest checking the official ENS website (ens.domains), community forums (e.g., Discord), or reaching out to the ENS support team. Do *not* invent an answer. Example: "Based on the provided documentation, I can explain [aspect X mentioned in sources], but the specific details about [aspect Y not mentioned] are not covered. You might find more information on the official ENS website or by asking in their community forums."
    *   **If the question is clearly *not* related to ENS:** Politely state that you cannot answer the specific question asked because your purpose is to assist with questions about the Ethereum Name Service (ENS) based on its documentation. Example: "I cannot provide information about [User's Unrelated Topic], as I'm designed to answer questions specifically about the Ethereum Name Service (ENS) using its documentation. Do you have any questions about ENS?"
3.  **Cite sources accurately:** Use the corresponding number in square brackets immediately after the information derived from that source. Every factual statement requires a citation. Only cite sources listed below.
4.  **Format using Markdown:** Use newlines, sections, and formatting for readability. Be concise.
5.  **No Reference Section:** Do not add a 'References' or 'Sources' section at the end; this will be handled separately.

**EXAMPLE (Answerable Question):**
**User:** What is ENS?
**Assistant:** ENS stands for Ethereum Name Service. It is a decentralized naming system built on the Ethereum blockchain. [1] It maps human-readable names like 'alice.eth' to machine-readable identifiers such as Ethereum addresses, other cryptocurrency addresses, content hashes, and metadata. [2]

**TARGET AUDIENCE (Non-Technical):**
* Keep language simple.
* When applicable, suggest using the ENS manager app (app.ens.domains) over technical methods.
---
**SOURCES:**
{context_str}
---

**Query:** {query_str}
**Answer:**
"""

# Configuration
VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
VOYAGE_MODEL = "voyage-3-lite"
VOYAGE_DIMENSION = 512

# Configure the LLM
llm = OpenAI(model="gpt-4o-mini", temperature=0.7, api_key=OPENAI_API_KEY)

# Configure the embedding model - This will be moved to startup initialization
# embedding_model = VoyageEmbedding(
#    api_key=VOYAGE_API_KEY,
#    model_name=VOYAGE_MODEL,
#    embed_batch_size=10,
#    output_dimension=VOYAGE_DIMENSION,
# )

httpx.Client = httpx.Client(verify=False)  # Only if needed for SSL issues
logging.getLogger("openai").setLevel(logging.DEBUG)


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[Message]
    customerId: int


async def search_docs(query: str):
    global query_retriever

    # Check if the retriever was successfully initialized
    if query_retriever is None:
        logging.error("Retriever not initialized. Check application startup.")
        return {
            "main_content": SYSTEM_PROMPT,
            "sources": [],
            "source_map": {},
            "source_nodes": [],
            "context_with_citations": "",
        }

    # Time the actual retrieval operation
    retrieval_start_time = time.time()
    logging.debug(f"Starting retrieval for query: {query}")
    # Use the globally initialized retriever instead of creating a new one
    nodes_with_scores = await query_retriever.aretrieve(query)
    retrieval_end_time = time.time()
    logging.debug(
        f"Retrieval operation completed in {retrieval_end_time - retrieval_start_time:.4f} seconds"
    )

    # Time the postprocessing step
    postproc_start_time = time.time()
    # Apply similarity postprocessor to filter out low similarity results
    # postprocessor = SimilarityPostprocessor(similarity_cutoff=0.3)
    # nodes_with_scores = postprocessor.postprocess_nodes(nodes_with_scores)
    postproc_end_time = time.time()
    logging.debug(
        f"Postprocessing completed in {postproc_end_time - postproc_start_time:.4f} seconds"
    )

    # Check if we have any nodes
    if not nodes_with_scores:
        return {
            "main_content": SYSTEM_PROMPT,
            "sources": [],
            "source_map": {},
            "source_nodes": [],
            "context_with_citations": "",
        }

    # Time the citation formatting
    citation_start_time = time.time()
    # Format response with citations
    main_response = query  # We'll need to process the nodes to generate a response
    sources = []
    source_map = {}
    context_with_citations = []
    url_to_citation = {}
    citation_counter = 1

    # Extract source information from nodes and create context with citations
    for node_with_score in nodes_with_scores:
        node = node_with_score.node
        metadata = node.metadata
        url = metadata.get("url", "No URL available")
        display_url = url  # Initialize display_url

        # Convert API URL to regular GitHub URL for better readability
        if "api.github.com" in url:
            url = url.replace("api.github.com", "github.com").replace("/blob", "/tree")

        # Transform ENS docs GitHub URLs to docs.ens.domains and create display name
        if "github.com/ensdomains/docs" in url:
            # Extract the path after /src/pages/
            match = re.search(r"/src/pages/(.*?)(?:\.mdx?)?$", url)
            if match:
                path = match.group(1)
                url = f"https://docs.ens.domains/{path}"
                # Create display URL: "ensdomains/docs/last/two/parts"
                path_parts = path.split("/")
                display_parts = path_parts[-2:] if len(path_parts) > 1 else path_parts
                display_url = f"ensdomains/docs/{'/'.join(display_parts)}"

        # Transform ENSIPs GitHub URLs and create display name
        elif "github.com/ensdomains/ensips" in url:
            # Extract the ENSIP number
            match = re.search(r"/ensips/(\d+)\.md$", url)
            if match:
                ensip_number = match.group(1)
                url = f"https://docs.ens.domains/ensip/{ensip_number}"
                display_url = f"ensdomains/ensips/{ensip_number}"

        # Transform ENS support docs URLs and create display name
        elif "github.com/ensdomains/ens-support-docs" in url:
            # Extract the path after /docs/
            match = re.search(r"/docs/(.*?)(?:\.mdx?)?$", url)
            if match:
                path = match.group(1)
                # Remove 'core/' from the path if it exists
                path = path.replace("core/", "")
                display_url = f"ensdomains/ens-support-docs/{path}"

        # Use existing citation number if URL was already cited
        if url in url_to_citation:
            citation_num = url_to_citation[url]
        else:
            citation_num = citation_counter
            url_to_citation[url] = citation_num
            citation_counter += 1
            source_info = f"[{citation_num}] [{display_url}]({url})"
            source_map[citation_num] = source_info
            if source_info not in sources:
                sources.append(source_info)

        # Add the node's text with its citation number
        header_path = metadata.get("header_path", "")
        context_text = node.text

        if header_path:
            context_text = f"[Header: {header_path}]\n{context_text}"
        context_with_citations.append(f"[{citation_num}] {context_text}\n")

    citation_end_time = time.time()
    logging.debug(
        f"Citation formatting completed in {citation_end_time - citation_start_time:.4f} seconds"
    )

    return {
        "main_content": main_response,
        "sources": sources,
        "source_map": source_map,
        "source_nodes": [node_with_score.node for node_with_score in nodes_with_scores],
        "context_with_citations": "\n".join(context_with_citations),
    }


@router.post("/chat")
async def chat(request: ChatRequest):
    start_time = time.time()
    logging.debug(f"Chat request received for customer {request.customerId}")
    try:
        messages = request.messages
        customer_id = request.customerId

        if not messages or messages[-1].role != "user":
            raise HTTPException(
                status_code=400, detail="Last message is not a user message"
            )

        if not customer_id:
            raise HTTPException(status_code=400, detail="Customer ID is required")

        user_message = messages[-1].content

        # --- Timing for search_docs ---
        search_start_time = time.time()
        search_result = await search_docs(user_message)
        search_end_time = time.time()
        logging.debug(
            f"search_docs completed in {search_end_time - search_start_time:.4f} seconds"
        )
        # --- End Timing ---

        # --- Timing for prompt prep ---
        prep_start_time = time.time()
        # Format the system prompt with context and query
        formatted_system_prompt = SYSTEM_PROMPT.format(
            context_str=search_result["context_with_citations"], query_str=user_message
        )

        content = f"{formatted_system_prompt}"

        # Prepare chat history with system prompt
        chat_history = []
        chat_history.append(
            ChatMessage(
                role=MessageRole.SYSTEM,
                content=content,
            )
        )

        # Add all previous messages to maintain conversation flow
        for msg in messages:
            if msg.role == "user":
                chat_history.append(
                    ChatMessage(role=MessageRole.USER, content=msg.content)
                )
            elif msg.role == "assistant":
                # Remove the references section from the assistant message
                msg.content = re.sub(r"\n\n## References\n[\s\S]*", "", msg.content)
                chat_history.append(
                    ChatMessage(role=MessageRole.ASSISTANT, content=msg.content)
                )

        memory = ChatMemoryBuffer.from_defaults(chat_history=chat_history)

        chat_engine = SimpleChatEngine.from_defaults(llm=llm, memory=memory)
        prep_end_time = time.time()
        logging.debug(
            f"Prompt/History preparation completed in {prep_end_time - prep_start_time:.4f} seconds"
        )
        # --- End Timing ---

        async def generate_response():
            # --- Timing for LLM stream ---
            llm_stream_start_time = time.time()
            logging.debug("Initiating LLM stream...")
            try:
                response = await chat_engine.astream_chat(user_message)
                response_chunks = []

                async for message in response.async_response_gen():
                    response_chunks.append(message)
                    yield message

                cited_numbers = set()
                citations_in_chunk = re.findall(r"\[(\d+)\]", "".join(response_chunks))
                cited_numbers.update(int(num) for num in citations_in_chunk)

                # Add references
                sorted_cited_numbers = sorted(list(cited_numbers))

                final_sources = []
                logging.info("Context:")
                logging.info(search_result["context_with_citations"])
                for i in sorted_cited_numbers:
                    if i in search_result["source_map"]:
                        final_sources.append(search_result["source_map"][i])
                if final_sources:
                    refs_header = "\n\n## References\n"
                    yield refs_header

                    for source in final_sources:
                        yield source + "\n"

            finally:
                # Log time after stream is fully processed
                llm_stream_end_time = time.time()
                logging.debug(
                    f"LLM stream processing completed in {llm_stream_end_time - llm_stream_start_time:.4f} seconds"
                )
            # --- End Timing ---

        total_setup_time = time.time() - start_time
        logging.debug(
            f"Chat setup (before streaming) completed in {total_setup_time:.4f} seconds"
        )
        return StreamingResponse(
            generate_response(),
            media_type="text/plain",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    except Exception as e:
        logging.error(f"Error in chat endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
