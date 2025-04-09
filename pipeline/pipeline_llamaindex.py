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
from llama_index.core import Document, Settings, StorageContext, VectorStoreIndex
from llama_index.core.node_parser import MarkdownNodeParser
from llama_index.vector_stores.postgres import PGVectorStore
from llama_index.embeddings.voyageai import VoyageEmbedding

# Need llama-hub loader for GitHub
# Ensure llama-hub is installed: pip install llama-hub
# May require git executable in path
from llama_index.readers.github import GithubRepositoryReader, GithubClient

# Database connection (SQLAlchemy is common with LlamaIndex PGVectorStore)
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
CHUNK_SIZE = 512  # Target size in tokens for LlamaIndex parser

# --- Database Setup ---
if not DB_CONN_STRING:
    raise ValueError("DATABASE_URL environment variable not set.")

db_url = make_url(DB_CONN_STRING)
# Set default port to 5432 if not specified
if db_url.port is None:
    db_url = db_url.set(port=5432)
db_schema_name = "public"

# table name is data_processed_chunks
# # PGVECTOR authomatically adds data_ to the table name
db_table_name = "processed_chunks"  # This is the 512-dim table


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
def run_ingestion_for_target(target: Dict[str, Any]):
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
        documents = reader.load_data(branch="master")  # Try master instead of main
        logging.info(f"[{customer_id}] Loaded {len(documents)} documents.")
        if not documents:
            logging.warning(
                f"[{customer_id}] No documents found for target {repo_url}. Skipping."
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

        # Node Parser (Markdown specific)
        node_parser = MarkdownNodeParser(
            include_metadata=True,
            include_prev_next_rel=True,
            header_path_separator="/",
        )  # Using default settings

        # Vector Store
        vector_store = PGVectorStore.from_params(
            database=db_url.database,
            host=db_url.host,
            password=db_url.password,
            port=db_url.port,
            user=db_url.username,
            table_name=db_table_name,
            schema_name=db_schema_name,
            embed_dim=VOYAGE_DIMENSION,  # Crucial: Match your embedding model
        )

        # Contexts
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        # Service Context or Settings (depending on LlamaIndex version)
        # Newer approach using global settings:
        Settings.llm = None  # Not needed for indexing
        Settings.embed_model = embed_model
        Settings.node_parser = node_parser
        # Older approach:
        # service_context = ServiceContext.from_defaults(
        #     llm=None, # Not needed for indexing
        #     embed_model=embed_model,
        #     node_parser=node_parser
        # )

    except Exception as e:
        logging.error(
            f"[{customer_id}] Failed to initialize LlamaIndex components: {e}",
            exc_info=True,
        )
        return

    # 3. Parse Documents into Nodes & Add Metadata
    # LlamaIndex does parsing implicitly when building the index,
    # but we might want to intercept nodes to add metadata.
    # An alternative is to parse first, enrich metadata, then index nodes.

    try:
        logging.info(f"[{customer_id}] Parsing documents into nodes...")
        # Use the node_parser explicitly to get nodes before indexing
        nodes = node_parser.get_nodes_from_documents(documents)
        logging.info(f"[{customer_id}] Generated {len(nodes)} nodes.")

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
        # This performs embedding and storage
        # Pass nodes directly if already parsed and enriched
        index = VectorStoreIndex(
            nodes=enriched_nodes,
            storage_context=storage_context,
            # service_context=service_context # Older LlamaIndex
            # Settings are used globally in newer versions
            show_progress=True,
        )
        logging.info(f"[{customer_id}] Index update complete for {repo_url}.")

    except Exception as e:
        # Catch potential embedding errors or DB errors during indexing
        logging.error(
            f"[{customer_id}] Failed to build/update index for {repo_url}: {e}",
            exc_info=True,
        )


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
    ]
    if not targets:
        logging.warning("No valid targets found. Exiting.")
        return

    # Run ingestion for each target sequentially for simplicity in V1 worker
    # Can parallelize later if needed, but manage resources carefully
    for target in targets:
        run_ingestion_for_target(target)

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
