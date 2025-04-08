import logging
import json
import os
from typing import List, Dict, Any

import psycopg2
from psycopg2.extras import execute_values
from pgvector.psycopg2 import register_vector

# Import config variables
from .config import DB_CONN_STRING, POOL_SIZE

# --- Database Connection Pool ---
# Simple pooling example; use SQLAlchemy or a more robust pool for production
db_conn_pool = []


def get_db_conn():
    """Gets a connection from the pool or creates new ones."""
    global db_conn_pool
    if not db_conn_pool:
        # Initialize pool
        for _ in range(POOL_SIZE):
            try:
                conn = psycopg2.connect(DB_CONN_STRING)
                register_vector(conn)  # Register pgvector extension
                db_conn_pool.append(conn)
            except Exception as e:
                logging.error(f"Failed to connect to DB: {e}")
                # Handle connection error appropriately
                raise

    # Basic round-robin / availability check (replace with proper pooling)
    # In a real app, use a library like psycopg2.pool or SQLAlchemy
    conn = db_conn_pool.pop(0)
    try:
        # Check if connection is still valid
        cur = conn.cursor()
        cur.execute("SELECT 1;")
        cur.close()
    except psycopg2.OperationalError:
        logging.warning("Stale DB connection detected, reconnecting.")
        try:
            conn.close()
        except:  # Handle case where connection is already closed
            pass
        conn = psycopg2.connect(DB_CONN_STRING)
        register_vector(conn)

    db_conn_pool.append(conn)  # Put back in pool
    return conn


def return_db_conn(conn):
    """Returns a connection to the pool (simplified)."""
    # In a real pool manager, this would handle returning the connection.
    # For this simple list-based pool, get_db_conn handles rotation.
    pass


# --- Database Operations ---
def get_targets_from_db() -> List[Dict[str, Any]]:
    """Fetches customer targets (repos, folders, tokens) from the database."""
    # This needs robust implementation: query your customer/config table
    logging.info("Fetching targets from DB...")
    # Example: Fetch customer_id, repo_url ('owner/repo'), folders_json, github_token
    # Ensure github_token is retrieved securely and is valid (e.g., refreshed installation token)
    # Dummy data - REPLACE WITH ACTUAL DB QUERY
    targets = [
        {
            "customer_id": 1,
            "repo_url": "ensdomains/docs",
            "folders": ["docs/"],
            "token": os.environ.get(
                "CUSTOMER_1_GITHUB_TOKEN"
            ),  # Still reading env var here, ideally from config table
        },
        # {'customer_id': 2, 'repo_url': 'ethereum/EIPs', 'folders': ['EIPS/'], 'token': os.environ.get("CUSTOMER_2_GITHUB_TOKEN")},
    ]
    # Filter out targets without tokens for safety
    valid_targets = [t for t in targets if t.get("token")]
    if len(valid_targets) != len(targets):
        logging.warning("Some targets skipped due to missing GitHub tokens.")
    return valid_targets


def store_chunks_in_db(chunks_data: List[Dict[str, Any]]):
    """Stores processed chunks with embeddings and metadata in the database."""
    if not chunks_data:
        return
    logging.info(f"Storing {len(chunks_data)} chunks in DB...")
    conn = None
    try:
        conn = get_db_conn()
        with conn.cursor() as cur:
            # Use execute_values for efficient bulk insertion
            # Ensure your table schema matches: customer_id, source_path, chunk_text, embedding (vector type), metadata (jsonb)
            sql = """
                INSERT INTO processed_chunks (customer_id, source_path, chunk_text, embedding, metadata)
                VALUES %s
                ON CONFLICT (customer_id, source_path, chunk_text) DO NOTHING;
            """  # Example: Add ON CONFLICT or specific upsert logic if needed

            # Prepare data tuples for execute_values
            values_list = [
                (
                    c["customer_id"],
                    c["source_path"],
                    c["chunk_text"],
                    c["embedding_vector"],  # Already list[float]
                    json.dumps(
                        c["metadata_json"]
                    ),  # Convert metadata dict to JSON string for JSONB column
                )
                for c in chunks_data
            ]

            execute_values(cur, sql, values_list, page_size=100)  # Adjust page_size
        conn.commit()
        logging.info(f"Successfully stored {len(chunks_data)} chunks.")
    except psycopg2.DatabaseError as e:
        logging.error(f"Database error during storage: {e}")
        if conn:
            conn.rollback()  # Rollback on error
        # Consider adding chunks to a retry queue or logging failed chunks
        raise  # Re-raise after logging
    except Exception as e:
        logging.error(f"Unexpected error during storage: {e}")
        if conn:
            conn.rollback()
        raise  # Re-raise after logging
    finally:
        if conn:
            # Simplified return for list-based pool
            pass  # get_db_conn handles putting it back
