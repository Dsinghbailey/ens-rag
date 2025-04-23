from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List
import os
import re
import logging
from llama_index.embeddings.voyageai import VoyageEmbedding
from llama_index.core import (
    StorageContext,
    load_indices_from_storage,
    Settings,
)
from llama_index.core.chat_engine import SimpleChatEngine
from llama_index.llms.openai import OpenAI
from llama_index.core.types import ChatMessage, MessageRole
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.postprocessor import SimilarityPostprocessor
from llama_index.core.retrievers import QueryFusionRetriever
from dotenv import load_dotenv

load_dotenv()
# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

router = APIRouter()

# Constants
OUT_OF_SCOPE_PROMPT = "I'm sorry, I'm not sure about that. You can reach out to the ENS team at [https://chat.ens.domains](https://chat.ens.domains)"
SYSTEM_PROMPT = """
**You are an AI assistant answering questions strictly based on the provided ENS documentation sources ONLY.**
Your primary goal is accuracy based *solely* on the numbered sources below.

**CRITICAL RULES:**
1.  **DO NOT USE EXTERNAL KNOWLEDGE.** Base your entire answer *only* on the information explicitly present in the numbered sources provided in the 'SOURCES' section below.
2.  **If the answer cannot be found within the 'SOURCES' section, DO NOT MAKE ONE UP.** Instead, output *only* the exact phrase `[OUT_OF_SCOPE]` and nothing else. Your confidence must be extremely high, derived directly from the source text.
3.  **Cite sources accurately:** Use the corresponding number in square brackets immediately after the information derived from that source. Every factual statement requires a citation. Only cite sources listed below.
4.  **Format using Markdown:** Use newlines, sections, and formatting for readability. Be concise.
5.  **Do not add a 'References' section at the end.** This will be handled separately.

**EXAMPLE:**
**User:** What is ENS?
**Assistant:** ENS is a decentralized naming system for the Ethereum blockchain. [1]

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

# Configure the embedding model
embedding_model = VoyageEmbedding(
    api_key=VOYAGE_API_KEY,
    model_name=VOYAGE_MODEL,
    embed_batch_size=10,
    output_dimension=VOYAGE_DIMENSION,
)


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[Message]
    customerId: int


async def search_docs(query: str):
    # Set the embedding model globally
    Settings.embed_model = embedding_model

    # Load index from persisted storage
    storage_context = StorageContext.from_defaults(persist_dir="./api/storage/1")

    # Load all indices
    indices = load_indices_from_storage(storage_context)
    if not indices:
        return {
            "is_out_of_scope": True,
            "main_content": OUT_OF_SCOPE_PROMPT,
            "sources": [],
            "source_map": {},
            "source_nodes": [],
            "context_with_citations": "",
        }

    # Create retrievers for each index
    retrievers = [index.as_retriever() for index in indices]

    # Create a fusion retriever
    retriever = QueryFusionRetriever(
        retrievers,
        similarity_top_k=5,
        num_queries=1,  # set to 1 to disable query generation  - it's bad
        use_async=True,
        verbose=True,
    )

    # Retrieve nodes using the fusion retriever
    nodes_with_scores = await retriever.aretrieve(query)

    # Apply similarity postprocessor to filter out low similarity results
    postprocessor = SimilarityPostprocessor(similarity_cutoff=0.4)
    nodes_with_scores = postprocessor.postprocess_nodes(nodes_with_scores)

    # Check if we have any nodes
    if not nodes_with_scores:
        return {
            "is_out_of_scope": True,
            "main_content": OUT_OF_SCOPE_PROMPT,
            "sources": [],
            "source_map": {},
            "source_nodes": [],
            "context_with_citations": "",
        }

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
        context_with_citations.append(f"[{citation_num}] {context_text}")

    return {
        "is_out_of_scope": len(sources) == 0,
        "main_content": main_response,
        "sources": sources,
        "source_map": source_map,
        "source_nodes": [node_with_score.node for node_with_score in nodes_with_scores],
        "context_with_citations": "\n".join(context_with_citations),
    }


@router.post("/chat")
async def chat(request: ChatRequest):
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
        search_result = await search_docs(user_message)

        # If the search result is out of scope, return the out of scope message directly
        if search_result["is_out_of_scope"]:
            logging.info("Response type: Out of scope")

            async def generate_out_of_scope_response():
                yield OUT_OF_SCOPE_PROMPT

                # Add links section if there are sources
                if search_result["sources"]:
                    links_header = "\n\n## Potentially Useful Links\n"
                    yield links_header

                # Add each source
                for source in search_result["sources"]:
                    yield source + "\n"

            return StreamingResponse(
                generate_out_of_scope_response(),
                media_type="text/plain",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
            )

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
        chat_engine = SimpleChatEngine.from_defaults(
            llm=llm,
            memory=memory,
            system_prompt=f"{SYSTEM_PROMPT}",
        )

        async def generate_response():
            response = await chat_engine.astream_chat(user_message)
            out_of_scope_detected = False
            response_chunks = []
            chunk_count = 0
            accumulated_text = ""

            # Check first 5 chunks for out-of-scope indicator
            async for message in response.async_response_gen():
                response_chunks.append(message)
                chunk_count += 1

                # Only check first 5 chunks for out-of-scope
                if chunk_count <= 5:
                    accumulated_text += message
                    # Check if the accumulated text contains the out-of-scope indicator
                    if "[OUT_OF_SCOPE]" in accumulated_text:
                        out_of_scope_detected = True
                        break
                elif chunk_count == 6:
                    yield accumulated_text
                    yield message
                else:
                    yield message

            # If out of scope was detected in first 5 chunks, return the out of scope prompt
            if out_of_scope_detected:
                logging.info("Response type: Out of scope")
                yield OUT_OF_SCOPE_PROMPT

                links_header = "\n\n## Potentially Useful Links\n"
                yield links_header

                for source in search_result["sources"]:
                    yield source + "\n"
                return

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

        return StreamingResponse(
            generate_response(),
            media_type="text/plain",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    except Exception as e:
        logging.error(f"Error in chat endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
