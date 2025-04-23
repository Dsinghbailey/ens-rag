import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from api.routes import router as api_router
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI()

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
