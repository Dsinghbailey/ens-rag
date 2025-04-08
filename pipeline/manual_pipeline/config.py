import os

# --- Configuration ---
# Load from environment variables (set in Render)
# GITHUB_TOKEN should be fetched dynamically per customer usually
VOYAGE_API_KEY = os.environ.get("VOYAGE_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
DB_CONN_STRING = os.environ.get("DATABASE_URL")  # Provided by Render for managed DB

VOYAGE_API_URL = "https://api.voyageai.com/v1/embeddings"  # Confirm URL if different
VOYAGE_MODEL = "voyage-3-lite"  # As per user's example code
# Determine embedding dimension for voyage-3-lite (e.g., 1024 - VERIFY THIS from Voyage docs)
VOYAGE_DIMENSION = 1024
OPENAI_LLM_MODEL = "gpt-4o-mini"

# Chunking Parameters
MAX_CHUNK_TOKENS = (
    500  # Target size in tokens (adjust based on embedding model limits/performance)
)
# Use tiktoken to count accurately if needed, otherwise estimate with word/char count
# enc = tiktoken.get_encoding("cl100k_base") # Example tokenizer
HEADING_SPLIT_LEVEL = 3  # Split sections by H1, H2, H3
OVERLAP_SENTENCES = 1  # Number of sentences from *previous* text chunk to prepend

# Database Pooling
POOL_SIZE = 5

# Optional: OpenAI API URL (if needed elsewhere)
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
