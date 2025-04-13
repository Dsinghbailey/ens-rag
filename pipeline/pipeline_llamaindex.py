import os
import logging
import json
import requests
from typing import List, Dict, Any, Optional

# Load environment variables from .env file FIRST before any other imports
try:
    from dotenv import load_dotenv

    # Load from the exact path where .env exists
    dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
    load_dotenv(dotenv_path)
    print(f"Loaded .env file from {dotenv_path}")
    print(f"DATABASE_URL: {os.environ.get('DATABASE_URL') is not None}")
    print(f"VOYAGE_API_KEY: {os.environ.get('VOYAGE_API_KEY') is not None}")
    print(f"GITHUB_TOKEN: {os.environ.get('GITHUB_TOKEN') is not None}")
except ImportError:
    print("dotenv package not found, skipping .env loading")

# LlamaIndex components
from llama_index.core import (
    Document,
    Settings,
    StorageContext,
    VectorStoreIndex,
    load_index_from_storage,
)
from llama_index.core.node_parser import MarkdownNodeParser
from llama_index.vector_stores.postgres import PGVectorStore
from llama_index.embeddings.voyageai import VoyageEmbedding
from llama_index.llms.openai import OpenAI

# Need llama-hub loader for GitHub
# Ensure llama-hub is installed: pip install llama-hub
# May require git executable in path
from llama_index.readers.github import GithubRepositoryReader, GithubClient

from sqlalchemy import make_url, create_engine, text
from sqlalchemy.exc import SQLAlchemyError

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# --- Configuration ---
VOYAGE_API_KEY = os.environ.get("VOYAGE_API_KEY")
OPENAI_API_KEY = os.environ.get(
    "OPENAI_API_KEY"
)  # Still needed if using OpenAI embedder fallback or for AI metadata
DB_CONN_STRING = os.environ.get(
    "DATABASE_URL"
)  # e.g., "postgresql://user:pass@host:port/dbname"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

VOYAGE_API_URL = "https://api.voyageai.com/v1/embeddings"
VOYAGE_MODEL = "voyage-3-lite"
VOYAGE_DIMENSION = 512

# Chunking / Parsing Parameters
CHUNK_SIZE = 2048  # Target size in tokens for LlamaIndex parser

# --- Database Setup ---
# if not DB_CONN_STRING:
#     raise ValueError("DATABASE_URL environment variable not set.")

# db_url = make_url(DB_CONN_STRING)
# # Set default port to 5432 if not specified
# if db_url.port is None:
#     db_url = db_url.set(port=5432)
# db_schema_name = "public"

# # table name is data_processed_chunks
# # # PGVECTOR authomatically adds data_ to the table name
# db_table_name = "processed_chunks"  # This is the 512-dim table


# --- Metadata Extraction Logic ---
# Example: Basic extractor integrated with LlamaIndex later if needed,
# or applied after loading documents.
def extract_md_metadata(nodes: List[Any], customer_id: int) -> List[Any]:
    """Adds custom metadata to LlamaIndex Nodes."""
    for node in nodes:
        # Basic metadata from Node/Document should exist (e.g., file_path)
        metadata = node.metadata or {}

        # Add customer ID
        metadata["customer_id"] = customer_id

        # Source URL (if file_path is from GithubReader, it might be usable)
        # Assuming file_path looks like 'owner/repo/docs/folder/file.md'
        # This needs refining based on GithubReader output format
        if "file_path" in metadata:
            # Attempt to reconstruct github url (needs repo_url base) - THIS IS FRAGILE
            # It's better if GithubReader stores the full URL or repo context
            # metadata['source_url'] = f"https://github.com/{metadata['file_path']}" # Placeholder - FIX THIS
            metadata["source_url"] = metadata.get(
                "file_path", "unknown_source"
            )  # Use file_path for now
        else:
            metadata["source_url"] = "unknown_source"

        # Heading context - MarkdownNodeParser *might* add this, check its output
        # If not, would need custom NodeParser or post-processing
        metadata["parent_headings"] = metadata.get(
            "parent_headings", {}
        )  # Rely on parser or add later

        # Chunk type guess - MarkdownNodeParser might add this, check its output
        metadata["chunk_type"] = metadata.get(
            "chunk_type", "text"
        )  # Rely on parser or add later

        # Code language - MarkdownNodeParser *should* extract this for code blocks
        metadata["code_language"] = metadata.get("code_language", None)

        # Basic Keywords (simple example)
        text = node.get_content()
        words = [w.lower() for w in text.split() if len(w) > 4 and w.isalnum()]
        keywords = list(set(words[:15]))
        # Add EIP/RFC/Address regex if needed (as before)
        import re

        eips = re.findall(r"\bEIP-\d+\b", text, re.IGNORECASE)
        if eips:
            keywords.extend([eip.upper() for eip in eips])

        metadata["keywords"] = list(set(keywords))

        # --- Optional AI Metadata Call ---
        # try:
        #     ai_meta = extract_ai_metadata(text) # Function defined previously
        #     metadata.update(ai_meta)
        # except Exception as e:
        #     logging.warning(f"Failed AI metadata for node {node.node_id}: {e}")
        # --- End Optional ---

        node.metadata = metadata
    return nodes


# --- Main Ingestion Function ---
def run_ingestion_for_target(
    target: Dict[str, Any], storage_context: Optional[StorageContext] = None
):
    """Runs the LlamaIndex ingestion pipeline for a single customer target."""
    customer_id = target["customer_id"]
    repo_url = target["repo_url"]  # format 'owner/repo'
    folders = target["folders"]
    token = target["token"]

    logging.info(f"[{customer_id}] Starting ingestion for {repo_url}")

    try:
        owner, repo = repo_url.split("/")[
            -2:
        ]  # Basic split, assumes 'owner/repo' format
    except ValueError:
        logging.error(
            f"[{customer_id}] Invalid repo_url format: {repo_url}. Expected 'owner/repo'. Skipping."
        )
        return

    # 1. Load Documents from GitHub
    try:
        # Debug GitHub token
        token_preview = (
            token[:4] + "..." + token[-4:] if len(token) > 8 else "too short"
        )
        logging.info(
            f"[{customer_id}] Using GitHub token: {token_preview}, length: {len(token)}"
        )

        # Check for URL encoding in the token
        if "%" in token:
            logging.warning(
                f"[{customer_id}] GitHub token contains URL-encoded characters, attempting to decode"
            )
            import urllib.parse

            token = urllib.parse.unquote(token)
            token_preview = (
                token[:4] + "..." + token[-4:] if len(token) > 8 else "too short"
            )
            logging.info(
                f"[{customer_id}] Decoded token length: {len(token)}, preview: {token_preview}"
            )

        # Create a GitHub client first
        github_client = GithubClient(github_token=token)

        # Then create the repository reader
        reader = GithubRepositoryReader(
            github_client=github_client,
            owner=owner,
            repo=repo,
            filter_directories=(folders, GithubRepositoryReader.FilterType.INCLUDE),
            filter_file_extensions=(
                [".md", ".mdx"],
                GithubRepositoryReader.FilterType.INCLUDE,
            ),
            verbose=True,
            concurrent_requests=5,
        )
        # Load data for the default branch (e.g., main/master)
        logging.info(f"[{customer_id}] Loading documents from {owner}/{repo}...")
        # Try 'main' first, then 'master' if main fails
        documents = []
        branches_to_try = ["main", "master"]
        for branch in branches_to_try:
            try:
                documents = reader.load_data(branch=branch)
                if documents:
                    logging.info(
                        f"[{customer_id}] Successfully loaded from '{branch}' branch"
                    )
                    break
            except Exception as e:
                logging.warning(
                    f"[{customer_id}] Failed to load from '{branch}' branch: {e}"
                )

        logging.info(f"[{customer_id}] Loaded {len(documents)} documents.")
        if not documents:
            logging.warning(
                f"[{customer_id}] No documents found for target {repo_url} in any branch. Skipping."
            )
            return
    except Exception as e:
        logging.error(
            f"[{customer_id}] Failed to load documents from GitHub repo {repo_url}: {e}",
            exc_info=True,
        )
        return

    # 2. Setup LlamaIndex Components
    try:
        logging.info(f"[{customer_id}] Setting up LlamaIndex components...")
        # Embedding Model
        embed_model = VoyageEmbedding(
            api_key=VOYAGE_API_KEY,
            model_name=VOYAGE_MODEL,
            embed_batch_size=10,  # Optional: adjust batch size as needed
        )

        # LLM
        llm = OpenAI(
            api_key=OPENAI_API_KEY,
            model="gpt-4o-mini",
            temperature=0.7,
        )

        # Node Parser (Markdown specific)
        node_parser = MarkdownNodeParser(
            include_metadata=True,
            include_prev_next_rel=True,
            header_path_separator="/",
        )  # Using default settings

        # Create or use existing storage context
        # Get the absolute path to the storage directory
        base_dir = os.path.dirname(os.path.abspath(__file__))
        persist_dir = os.path.join(base_dir, "storage", str(customer_id))
        print(f"[{customer_id}] Persist directory: {persist_dir}")
        # Ensure the storage directory exists
        os.makedirs(persist_dir, exist_ok=True)

        if storage_context is None:
            # Check if we have existing storage files
            docstore_path = os.path.join(persist_dir, "docstore.json")
            if not os.path.exists(docstore_path):
                # If no existing storage, create a fresh storage context
                storage_context = StorageContext.from_defaults()
                # Initialize the storage directory
                storage_context.persist(persist_dir=persist_dir)
            else:
                # Load existing storage context
                storage_context = StorageContext.from_defaults(persist_dir=persist_dir)

        # Service Context or Settings (depending on LlamaIndex version)
        # Newer approach using global settings:
        Settings.llm = llm
        Settings.embed_model = embed_model
        Settings.node_parser = node_parser

    except Exception as e:
        logging.error(
            f"[{customer_id}] Failed to initialize LlamaIndex components: {e}",
            exc_info=True,
        )
        return

    # 3. Parse Documents into Nodes & Add Metadata
    try:
        logging.info(f"[{customer_id}] Parsing documents into nodes...")
        # Use the node_parser explicitly to get nodes before indexing
        nodes = node_parser.get_nodes_from_documents(documents)

        # Post-process nodes to merge small nodes with their following content
        min_length = 500  # Define a minimum length for nodes
        merged_nodes = []
        current_node = None
        for node in nodes:
            if current_node is None:
                current_node = node
            else:
                # Merge nodes if the current node is too short
                if len(current_node.text) < min_length:
                    current_node.text += " " + node.text
                else:
                    merged_nodes.append(current_node)
                    current_node = node
        # Add the last node if it exists
        if current_node is not None:
            merged_nodes.append(current_node)
        logging.info(
            f"Generated {len(merged_nodes)} nodes after merging {len(nodes)} small nodes."
        )
        nodes = merged_nodes

        logging.info(f"[{customer_id}] Extracting and adding metadata to nodes...")
        # Enrich nodes with custom metadata
        enriched_nodes = extract_md_metadata(nodes, customer_id)
        logging.info(f"[{customer_id}] Metadata enrichment complete.")

        # Add this before creating the index
        if enriched_nodes:
            # Get first embedding to check dimension
            first_embedding = embed_model.get_text_embedding(
                enriched_nodes[0].get_content()
            )
            logging.info(
                f"[{customer_id}] First embedding dimension: {len(first_embedding)}"
            )

    except Exception as e:
        logging.error(
            f"[{customer_id}] Failed during node parsing or metadata extraction: {e}",
            exc_info=True,
        )
        return

    # 4. Build / Update the Index
    try:
        logging.info(f"[{customer_id}] Building or updating vector store index...")

        # Create a new index with the current nodes
        index = VectorStoreIndex(
            nodes=enriched_nodes,
            storage_context=storage_context,
            show_progress=True,
        )

        # Persist the index
        index.storage_context.persist(persist_dir=persist_dir)
        logging.info(f"[{customer_id}] Index update complete for {repo_url}.")

        return storage_context  # Return the storage context for reuse

    except Exception as e:
        # Catch potential embedding errors or DB errors during indexing
        logging.error(
            f"[{customer_id}] Failed to build/update index for {repo_url}: {e}",
            exc_info=True,
        )
        return storage_context  # Return storage context even on error


# --- Main Orchestration ---
def run_pipeline():
    logging.info("Starting LlamaIndex ingestion pipeline...")
    targets = [
        {
            "customer_id": 1,
            "repo_url": "ensdomains/docs",
            "folders": ["src/"],
            "token": GITHUB_TOKEN,
        },
        {
            "customer_id": 1,
            "repo_url": "ensdomains/ensips",
            "folders": ["ensips/"],
            "token": GITHUB_TOKEN,
        },
        {
            "customer_id": 1,
            "repo_url": "ensdomains/ens-support-docs",
            "folders": ["docs/"],
            "token": GITHUB_TOKEN,
        },
    ]
    if not targets:
        logging.warning("No valid targets found. Exiting.")
        return

    # Initialize storage context for the first target
    storage_context = None

    # Run ingestion for each target, passing the storage context between them
    for target in targets:
        storage_context = run_ingestion_for_target(target, storage_context)

    logging.info("LlamaIndex ingestion pipeline finished.")


if __name__ == "__main__":
    if not VOYAGE_API_KEY or not DB_CONN_STRING:
        logging.error(
            "Missing essential environment variables (VOYAGE_API_KEY, DATABASE_URL)"
        )
    else:
        # Optional: Run DB schema setup if needed (e.g., using Alembic or SQL)
        # Ensure pgvector is enabled: CREATE EXTENSION IF NOT EXISTS vector;
        run_pipeline()
