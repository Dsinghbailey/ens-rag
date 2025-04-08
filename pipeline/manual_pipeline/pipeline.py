import os
import json
import concurrent.futures
from typing import List, Dict, Any, Tuple
import logging

# Import components from other modules
from .. import config
from .db import get_targets_from_db, store_chunks_in_db
from .github import fetch_repo_files
from .parsing import chunk_markdown_with_overlap
from .embedding import get_voyage_embedding

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


# --- Worker Function ---
def process_file(
    file_path_and_content: Tuple[str, str], customer_id: int
) -> List[Dict[str, Any]]:
    """Processes a single markdown file: chunks, extracts metadata. Returns dicts ready for embedding."""
    source_identifier, file_content = file_path_and_content
    logging.info(f"[{customer_id}] Starting processing for {source_identifier}")
    processed_chunks_for_embedding = []
    try:
        # Use the chunking function from the parsing module
        chunks = chunk_markdown_with_overlap(file_content, source_identifier)

        for chunk in chunks:
            if (
                chunk.get("text") and len(chunk.get("text")) > 10
            ):  # Basic quality filter
                # Metadata is already extracted within chunk_markdown_with_overlap
                processed_chunks_for_embedding.append(
                    {
                        "customer_id": customer_id,
                        "source_path": source_identifier,  # source_url is inside metadata
                        "chunk_text": chunk["text"],
                        "metadata_json": chunk["metadata"],
                    }
                )
            else:
                logging.warning(
                    f"[{customer_id}] Skipping very short or empty chunk from {source_identifier}"
                )

    except Exception as e:
        logging.error(
            f"[{customer_id}] Error processing file {source_identifier}: {e}",
            exc_info=True,  # Log traceback
        )

    logging.info(
        f"[{customer_id}] Finished processing {source_identifier}, found {len(processed_chunks_for_embedding)} chunks for embedding."
    )
    return processed_chunks_for_embedding


# --- Main ETL Orchestration ---
def run_ingestion():
    logging.info("Starting ingestion process...")
    # 1. Get targets from DB
    try:
        targets = get_targets_from_db()
    except Exception as e:
        logging.error(f"Failed to get targets from database: {e}", exc_info=True)
        return  # Cannot proceed without targets

    if not targets:
        logging.warning("No valid targets found in DB. Exiting.")
        return

    # 2. Fetch files concurrently
    all_files_to_process: Dict[int, List[Tuple[str, str]]] = (
        {}
    )  # {customer_id: [(path, content), ...]}
    # Consider adjusting max_workers based on resource limits and type of operation (I/O bound)
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=5, thread_name_prefix="GitFetcher"
    ) as executor:
        future_to_target = {
            executor.submit(
                fetch_repo_files,
                t["repo_url"],
                t["folders"],
                t["token"],
                t["customer_id"],
            ): t
            for t in targets
        }
        for future in concurrent.futures.as_completed(future_to_target):
            target = future_to_target[future]
            customer_id = target["customer_id"]
            try:
                markdown_files = future.result()
                if markdown_files:
                    if customer_id not in all_files_to_process:
                        all_files_to_process[customer_id] = []
                    # Ensure items are tuples (source_identifier, content)
                    all_files_to_process[customer_id].extend(
                        list(markdown_files.items())
                    )
            except Exception as exc:
                logging.error(
                    f"Target {target['repo_url']} generated an exception during fetch: {exc}",
                    exc_info=True,
                )

    if not all_files_to_process:
        logging.warning(
            "No markdown files found for any target after fetch step. Exiting."
        )
        return

    # 3. Process files (Chunking & Metadata) concurrently
    all_chunks_to_embed: List[Dict[str, Any]] = []
    # Use ProcessPoolExecutor if parsing/metadata is CPU intensive and GIL becomes a bottleneck
    # Ensure functions in parsing.py are pickleable if using ProcessPoolExecutor
    # max_workers=os.cpu_count() can be aggressive, consider lower number like os.cpu_count() // 2
    with concurrent.futures.ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
        # Or ThreadPoolExecutor if primary bottleneck is minor I/O within processing or regex
        # with concurrent.futures.ThreadPoolExecutor(max_workers=10, thread_name_prefix='FileProcessor') as executor:
        future_to_file = []
        for customer_id, files in all_files_to_process.items():
            logging.info(
                f"Submitting {len(files)} files for customer {customer_id} for processing..."
            )
            for file_info in files:  # file_info is tuple (source_identifier, content)
                if not isinstance(file_info, tuple) or len(file_info) != 2:
                    logging.warning(f"Skipping invalid file_info item: {file_info}")
                    continue
                future = executor.submit(process_file, file_info, customer_id)
                future_to_file.append(future)

        processed_file_count = 0
        for future in concurrent.futures.as_completed(future_to_file):
            try:
                processed_chunks = future.result()
                all_chunks_to_embed.extend(processed_chunks)
                processed_file_count += 1
            except Exception as exc:
                # Log error but continue processing other futures
                logging.error(
                    f"A file processing task generated an exception: {exc}",
                    exc_info=True,
                )
        logging.info(f"Completed processing for {processed_file_count} files.")

    if not all_chunks_to_embed:
        logging.warning("No chunks generated from processing files. Exiting.")
        return

    logging.info(f"Total chunks to embed: {len(all_chunks_to_embed)}")

    # 4. Get Embeddings (Batching is crucial)
    final_chunks_for_db = []
    batch_size = 128  # Adjust based on Voyage API limits and typical chunk size

    for i in range(0, len(all_chunks_to_embed), batch_size):
        batch_to_process = all_chunks_to_embed[i : i + batch_size]
        texts_to_embed = [chunk["chunk_text"] for chunk in batch_to_process]

        # Call embedding function from embedding module
        embeddings = get_voyage_embedding(texts_to_embed)

        if embeddings and len(embeddings) == len(batch_to_process):
            for chunk_data, embedding_vector in zip(batch_to_process, embeddings):
                chunk_data["embedding_vector"] = embedding_vector
                # Ensure metadata is serializable (should be handled in db.py or here before passing)
                try:
                    # Attempt to dump/load to validate and ensure basic types
                    chunk_data["metadata_json"] = json.loads(
                        json.dumps(chunk_data["metadata_json"], default=str)
                    )
                except (TypeError, json.JSONDecodeError) as e:
                    logging.error(
                        f"Metadata serialization error for chunk {chunk_data.get('source_path')}: {e}"
                    )
                    # Decide how to handle: skip chunk, store with error marker, etc.
                    # Skipping for now:
                    continue
                final_chunks_for_db.append(chunk_data)
        else:
            logging.error(
                f"Failed to get embeddings for batch starting at index {i}. Skipping batch."
            )
            # Optionally add failed chunks to a retry mechanism

    # 5. Store results in DB
    if final_chunks_for_db:
        try:
            # Call DB storage function from db module
            store_chunks_in_db(final_chunks_for_db)
        except Exception as e:
            logging.error(f"Failed to store chunks in database: {e}", exc_info=True)
            # Consider adding failed batches to a retry queue

    logging.info("Ingestion process finished.")


if __name__ == "__main__":
    # Example: Load .env file if present for local development
    try:
        from dotenv import load_dotenv

        # Determine the correct path to .env, assuming it's in the workspace root
        dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env")
        if os.path.exists(dotenv_path):
            load_dotenv(dotenv_path=dotenv_path)
            logging.info(f"Loaded .env file from: {dotenv_path}")
        else:
            # Try loading from current dir if not found one level up
            if os.path.exists(".env"):
                load_dotenv()
                logging.info("Loaded .env file from current directory")
            else:
                logging.info(".env file not found in expected locations.")

    except ImportError:
        logging.info(
            "python-dotenv not installed, cannot load .env file. Reading from environment."
        )

    # Validate essential config using imported config values
    # Reload config values *after* potentially loading .env
    from .. import config
    import importlib

    importlib.reload(config)  # Reload to pick up .env values

    if (
        not config.VOYAGE_API_KEY
        or not config.OPENAI_API_KEY
        or not config.DB_CONN_STRING
    ):
        missing_vars = []
        if not config.VOYAGE_API_KEY:
            missing_vars.append("VOYAGE_API_KEY")
        if not config.OPENAI_API_KEY:
            missing_vars.append("OPENAI_API_KEY")
        if not config.DB_CONN_STRING:
            missing_vars.append("DATABASE_URL")
        logging.error(
            f"Missing essential environment variables: {', '.join(missing_vars)}"
        )
        # Decide if to exit: raise SystemExit("Missing essential configuration.")
    else:
        # Optionally log loaded config (mask keys)
        logging.info(
            f"DB Connection String set: {'*' * 5 + config.DB_CONN_STRING[-4:] if config.DB_CONN_STRING else 'Not Set'}"
        )
        logging.info(f"Voyage Key set: {'Yes' if config.VOYAGE_API_KEY else 'No'}")
        logging.info(f"OpenAI Key set: {'Yes' if config.OPENAI_API_KEY else 'No'}")
        run_ingestion()
