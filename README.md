# Database Setup Instructions

## Prerequisites

- PostgreSQL 11 or later
- Required environment variables:
  - `DATABASE_URL`: PostgreSQL connection string (format: "postgresql://user:pass@host:port/dbname")
  - `VOYAGE_API_KEY`: Your Voyage AI API key
  - `GITHUB_TOKEN`: Your GitHub access token
  - `OPENAI_API_KEY`: (Optional) Only if using OpenAI as fallback

## Installing pgvector Extension

### Ubuntu/Debian

```bash
# Add PostgreSQL's repository
sudo apt install postgresql-common
sudo /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh

# Install pgvector
sudo apt install postgresql-15-pgvector  # Replace 15 with your PostgreSQL version
```

### macOS (Homebrew)

```bash
# Install pgvector
brew install pgvector

# Link pgvector to your PostgreSQL installation
# Replace 15 with your PostgreSQL version if different
brew link pgvector --force

# Restart PostgreSQL
brew services restart postgresql@15
```

## Database Setup

1. Connect to your PostgreSQL database
2. Create the vector extension:

```sql
CREATE EXTENSION vector;
```

3. The pipeline will automatically create the required table, but if you want to create it manually:

```sql
CREATE TABLE IF NOT EXISTS processed_chunks_llamaindex (
    id uuid PRIMARY KEY,
    embedding vector(512),
    document text,
    metadata jsonb
);

-- Optional: Add index for better search performance
CREATE INDEX ON processed_chunks_llamaindex USING ivfflat (embedding vector_cosine_ops);
```
