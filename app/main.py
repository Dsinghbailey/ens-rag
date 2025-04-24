import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from api.routes import router as api_router
from dotenv import load_dotenv
from contextlib import asynccontextmanager
import logging
from typing import List

# For initializing resources
from llama_index.embeddings.voyageai import VoyageEmbedding
from llama_index.core import (
    StorageContext,
    load_indices_from_storage,
    Settings,
)
from llama_index.core.retrievers import QueryFusionRetriever, BaseRetriever
from llama_index.retrievers.bm25 import BM25Retriever
from llama_index.core.tools import RetrieverTool
from api import routes as api_routes  # Import the module to access globals

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    logger.info("Application startup: Initializing resources...")
    persist_dir = "./api/storage/1"
    try:
        # 1. Initialize Embedding Model (as before)
        logger.info("Initializing embedding model...")
        api_routes.embedding_model = VoyageEmbedding(
            api_key=api_routes.VOYAGE_API_KEY,
            model_name=api_routes.VOYAGE_MODEL,
            output_dimension=api_routes.VOYAGE_DIMENSION,
        )
        Settings.embed_model = api_routes.embedding_model
        logger.info("Embedding model initialized.")

        # 2. Load Storage and Vector Indices/Retrievers
        logger.info(f"Loading indices and storage context from: {persist_dir}")
        storage_context = StorageContext.from_defaults(persist_dir=persist_dir)
        # Load potentially multiple vector indices
        vector_indices = load_indices_from_storage(storage_context)
        vector_retrievers: List[BaseRetriever] = []
        if not vector_indices:
            logger.warning("No vector indices found in storage.")
        else:
            logger.info(
                f"Found {len(vector_indices)} vector index(es). Creating retrievers..."
            )
            vector_retrievers = [
                index.as_retriever(similarity_top_k=5) for index in vector_indices
            ]
            logger.info(f"Created {len(vector_retrievers)} vector retriever(s).")

        # 3. Load Nodes and Create BM25 Retriever (operates across all nodes)
        logger.info("Creating BM25 retriever...")
        # BM25 still uses all nodes from the single docstore
        nodes = list(storage_context.docstore.docs.values())
        if not nodes:
            logger.warning("No nodes found in docstore for BM25 retriever!")
            bm25_retriever = None
        else:
            bm25_retriever = BM25Retriever.from_defaults(
                nodes=nodes, similarity_top_k=5  # Use all nodes
            )
            logger.info("BM25 retriever created.")

        # 4. Combine ALL Retrievers using QueryFusionRetriever
        retrievers = []  # Changed from retriever_tools
        # Add all vector retrievers
        retrievers.extend(vector_retrievers)
        # Add the BM25 retriever if it exists
        if bm25_retriever:
            retrievers.append(bm25_retriever)

        if not retrievers:
            logger.error("No retrievers available (neither vector nor BM25)!")
            api_routes.query_retriever = None
        else:
            logger.info(
                f"Creating QueryFusionRetriever with {len(retrievers)} retriever(s)."
            )
            api_routes.query_retriever = QueryFusionRetriever(
                retrievers,  # Pass the list of retrievers directly
                similarity_top_k=4,
                num_queries=1,
                mode="reciprocal_rerank",
                use_async=True,
                verbose=True,
            )
            logger.info("Hybrid QueryFusionRetriever created successfully.")

    except Exception as e:
        logger.exception("Failed to initialize resources during startup")
        api_routes.query_retriever = None

    # Application runs here
    yield

    # --- Shutdown ---
    logger.info("Application shutdown.")


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
