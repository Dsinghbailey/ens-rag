# ENS Documentation Chat

An AI-powered chat interface for ENS (Ethereum Name Service) documentation that enables users to ask questions and receive answers sourced from ENS-related GitHub repositories.

## Features

- Natural language Q&A with ENS documentation
- Accurate citations and references to sources
- Streaming responses for real-time feedback
- Mobile-friendly interface with responsive design
- Support for markdown and code syntax highlighting

## Technology Stack

- **Backend**: Python/FastAPI
- **Frontend**: React/TypeScript/Vite
- **AI**: OpenAI GPT-4o, Voyage AI embeddings
- **Document Processing**: LlamaIndex for document ingestion and retrieval

## Project Structure

This project uses a combined structure where the backend serves the frontend:

```
unrag/
├── app/                  # Main application directory
│   ├── api/              # API endpoints and backend logic
│   ├── static/           # Frontend build output (served as static files)
│   ├── main.py           # Entry point for the combined app
│   └── requirements.txt  # Python dependencies
├── build.sh              # Build script
└── frontend/             # Frontend source code
```

## Getting Started

### Prerequisites

- Node.js (v16+)
- Python (v3.11+)
- OpenAI API Key
- Voyage AI API Key

### Environment Variables

Create a `.env` file in the app folder with the following variables:

```
OPENAI_API_KEY=your_openai_key
VOYAGE_API_KEY=your_voyage_key
```

### Running in Development Mode

For development with hot reloading, you can run the frontend and backend separately:

1. **Start the app:**

```bash
cd app
python -m uvicorn main:app --host 0.0.0.0 --port 10000 --reload
```

2. **Start the frontend:**

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at http://localhost:3000 and will automatically proxy API requests to the backend at http://localhost:10000.

### Running in Production Mode

To run the combined application (frontend served by backend):

1. **Build the application:**

```bash
cd frontend
npm install
npm build
```

2. **Run the combined service:**

```bash
cd app
python main.py
```

The application will be available at http://localhost:10000.

## Deployment on Render

This application is configured for easy deployment on Render.com:

1. Push your code to a Git repository
2. In Render, create a new Web Service pointing to your repository
3. Use the following settings:
   - Build Command: `./build.sh`
   - Start Command: `cd app && python main.py`
   - Environment Variables: Set `OPENAI_API_KEY` and `VOYAGE_API_KEY`

## License

MIT

## Acknowledgements

- [Ethereum Name Service](https://ens.domains/)
- [LlamaIndex](https://www.llamaindex.ai/)
- [OpenAI](https://openai.com/)
- [Voyage AI](https://www.voyageai.com/)
