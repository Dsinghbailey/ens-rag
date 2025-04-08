import logging
import requests
from typing import List, Optional

# Import config variables
from .config import VOYAGE_API_KEY, VOYAGE_API_URL, VOYAGE_MODEL


# --- Embedding ---
def get_voyage_embedding(text_batch: List[str]) -> Optional[List[List[float]]]:
    """Gets embeddings for a BATCH of text chunks from Voyage AI."""
    if not text_batch:
        return []
    if not VOYAGE_API_KEY or not VOYAGE_API_URL:
        logging.error("Voyage API Key or URL not configured. Cannot get embeddings.")
        return None  # Indicate failure

    logging.info(
        f"Getting {len(text_batch)} embeddings from Voyage AI (model: {VOYAGE_MODEL})..."
    )
    try:
        response = requests.post(
            VOYAGE_API_URL,
            headers={
                "Authorization": f"Bearer {VOYAGE_API_KEY}",
                "Content-Type": "application/json",
                "Request-Source": "unrag-pipeline",  # Optional: Identify client
            },
            json={
                "model": VOYAGE_MODEL,
                "input": text_batch,
                "input_type": "document",  # Assuming text chunks are documents
            },
            timeout=60,  # Increased timeout for batch
        )
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        data = response.json()

        if (
            "data" in data
            and isinstance(data["data"], list)
            and len(data["data"]) == len(text_batch)
        ):
            embeddings = [item.get("embedding") for item in data["data"]]
            # Validate embeddings format (list of floats)
            if all(
                isinstance(emb, list) and all(isinstance(f, float) for f in emb)
                for emb in embeddings
            ):
                # Optional: Check dimension if config available
                # from .config import VOYAGE_DIMENSION
                # if VOYAGE_DIMENSION and any(len(emb) != VOYAGE_DIMENSION for emb in embeddings):
                #     logging.error(f"Voyage API returned embeddings with unexpected dimension.")
                #     return None # Or handle partial success
                return embeddings
            else:
                logging.error(
                    "Invalid embedding format received in Voyage response batch."
                )
                return None  # Indicate failure
        else:
            logging.error(
                f"Mismatch in batch size or missing/invalid 'data' field in Voyage response: {data}"
            )
            return None  # Indicate failure

    except requests.exceptions.Timeout:
        logging.error(f"Voyage API batch request timed out after 60 seconds.")
        return None  # Indicate failure
    except requests.exceptions.HTTPError as http_err:
        logging.error(f"HTTP error calling Voyage API batch: {http_err}")
        logging.error(
            f"Voyage API Response Status: {http_err.response.status_code}, Body: {http_err.response.text}"
        )
        return None  # Indicate failure
    except requests.exceptions.RequestException as req_err:
        logging.error(f"Request exception calling Voyage API batch: {req_err}")
        return None  # Indicate failure
    except Exception as e:
        logging.error(f"Unexpected error during batch embedding: {e}", exc_info=True)
        return None  # Indicate failure
