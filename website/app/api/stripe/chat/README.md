# Chat Response API with LlamaIndex.TS

This API route implements a conversational RAG system using LlamaIndex.TS with metadata-based re-ranking and streaming responses.

## Dependencies

Make sure the following dependencies are installed:

```bash
npm install llamaindex ai dotenv
```

## Configuration

The API requires the following environment variables:

- `OPENAI_API_KEY`: Your OpenAI API key
- `DATABASE_URL`: PostgreSQL connection string with pgvector extension

## Database Requirements

The database must have:

- The `pgvector` extension installed
- A table named `processed_chunks_llamaindex` with:
  - `id`: Primary key
  - `text`: Text content
  - `metadata_`: JSONB field with metadata
  - `embedding`: Vector field with 512 dimensions

## TypeScript Configuration

For proper type support, make sure your `tsconfig.json` allows importing modules without type declarations:

```json
{
  "compilerOptions": {
    "allowSyntheticDefaultImports": true,
    "noImplicitAny": false
  }
}
```

## API Usage

Send a POST request with the following JSON structure:

```json
{
  "query": "Your question here",
  "customerId": 123,
  "history": [
    { "role": "user", "content": "Previous question" },
    { "role": "assistant", "content": "Previous answer" }
  ]
}
```

The response will be streamed and include source citations at the end.
