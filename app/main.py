import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from api.routes import router as api_router
from dotenv import load_dotenv
from contextlib import asynccontextmanager
import logging

# For initializing resources
from llama_index.embeddings.voyageai import VoyageEmbedding
from llama_index.core import (
    StorageContext,
    load_indices_from_storage,
    Settings,
)
from llama_index.core.retrievers import QueryFusionRetriever
from api import routes as api_routes  # Import the module to access globals

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    logger.info("Application startup: Initializing resources...")
    try:
        # Initialize embedding model
        logger.info("Initializing embedding model...")
        api_routes.embedding_model = VoyageEmbedding(
            api_key=api_routes.VOYAGE_API_KEY,
            model_name=api_routes.VOYAGE_MODEL,
            embed_batch_size=10,
            output_dimension=api_routes.VOYAGE_DIMENSION,
        )
        # Set the global embedding model in Settings
        Settings.embed_model = api_routes.embedding_model
        logger.info("Embedding model initialized.")

        # Load index and create retriever
        logger.info("Loading index from storage...")
        storage_context = StorageContext.from_defaults(persist_dir="./api/storage/1")
        indices = load_indices_from_storage(storage_context)

        if not indices:
            logger.error(
                "No indices found in storage. Retriever will not be available."
            )
            # Keep query_retriever as None
        else:
            logger.info(f"Loaded {len(indices)} index(es). Creating retrievers...")
            # Create retrievers for each index
            base_retrievers = [index.as_retriever() for index in indices]

            # Create the fusion retriever
            api_routes.query_retriever = QueryFusionRetriever(
                base_retrievers,
                similarity_top_k=5,
                num_queries=1,  # Set to 1 to disable query generation
                use_async=True,
                verbose=True,
            )
            logger.info("QueryFusionRetriever created successfully.")

    except Exception as e:
        logger.exception("Failed to initialize resources during startup")
        # query_retriever remains None, search_docs will handle this

    # Application runs here
    yield

    # --- Shutdown ---
    logger.info("Application shutdown.")
    # No specific cleanup needed


app = FastAPI(lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the API routes
app.include_router(api_router, prefix="/api")

# Mount the static files (frontend build)
app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")


# Serve the index.html for all other routes
@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    # If the path exists in static, serve that file
    static_file_path = f"static/{full_path}"
    if os.path.isfile(static_file_path):
        return FileResponse(static_file_path)

    # Otherwise, serve index.html for client-side routing
    return FileResponse("static/index.html")


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
