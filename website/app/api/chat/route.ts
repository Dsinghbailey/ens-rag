import { NextRequest, NextResponse } from "next/server";
import { type Message } from "ai";
import { VoyageAIEmbedding } from "@llamaindex/voyage-ai";
import { SimpleChatEngine, VectorStoreIndex } from "llamaindex";
import { OpenAI } from "@llamaindex/openai";
import type { ChatMessage } from "@llamaindex/core/llms";
import { BaseEmbedding } from "@llamaindex/core/embeddings";
import { PGVectorStore } from "@llamaindex/core/vector-store";

const CUSTOMER_PROMPT = "You are trained on ENS documentation.";

const SYSTEM_PROMPT = `
  You are a helpful AI assistant.
  Always format your responses using markdown syntax.
  Be concise.
  Break them into sections when appropriate.
  Use newlines.
  Do not hallucinate.
  If you are unsure about the answer, say "I don't know".
`;

// Configure the LLM
const llm = new OpenAI({
  model: "gpt-4o-mini",
  temperature: 0.7,
  apiKey: process.env.OPENAI_API_KEY,
});

// Configure the embedding model
class VoyageEmbedding extends BaseEmbedding {
  private apiKey: string;
  private modelName: string;

  constructor() {
    super();
    this.apiKey = process.env.VOYAGE_API_KEY || "";
    this.modelName = "voyage-3-lite";
  }

  async getTextEmbedding(text: string): Promise<number[]> {
    const response = await fetch("https://api.voyageai.com/v1/embeddings", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${this.apiKey}`,
      },
      body: JSON.stringify({
        model: this.modelName,
        input: text,
      }),
    });

    const data = await response.json();
    return data.data[0].embedding;
  }

  async getTextEmbeddings(texts: string[]): Promise<number[][]> {
    return Promise.all(texts.map((text) => this.getTextEmbedding(text)));
  }
}

const embedModel = new VoyageEmbedding();

// Configure the vector store
const vectorStore = new PGVectorStore({
  host: process.env.PGHOST,
  port: parseInt(process.env.PGPORT || "5432"),
  user: process.env.PGUSER,
  password: process.env.PGPASSWORD,
  database: process.env.PGDATABASE,
  tableName: "processed_chunks",
  schemaName: "public",
  dimension: 512, // Voyage embedding dimension
});

// Add this function to handle vector store querying
async function searchDocs(query: string) {
  // Create index from existing vector store
  const index = await VectorStoreIndex.fromExistingVectorStore(
    vectorStore,
    embedModel
  );

  // Create a query engine
  const queryEngine = index.asQueryEngine();

  // Perform the search
  const response = await queryEngine.query({
    query,
    similarityTopK: 5, // Number of results to return
  });

  return response;
}

export async function POST(request: NextRequest) {
  try {
    const { messages, customerId } = (await request.json()) as {
      messages: Message[];
      customerId: number;
    };

    const userMessage = messages[messages.length - 1];
    if (!userMessage || userMessage.role !== "user") {
      return NextResponse.json(
        { detail: "Last message is not a user message" },
        { status: 400 }
      );
    }

    if (!customerId) {
      return NextResponse.json(
        { detail: "Customer ID is required" },
        { status: 400 }
      );
    }

    // Update the vector store querying section
    const searchResponse = await searchDocs(userMessage.content);

    // Add system message at the beginning of history if not already present
    const chatHistory = [...messages] as ChatMessage[];
    if (chatHistory.length === 0 || chatHistory[0].role !== "system") {
      chatHistory.unshift({
        content:
          SYSTEM_PROMPT +
          " " +
          CUSTOMER_PROMPT +
          "\n\nRelevant context:\n" +
          searchResponse.response,
        role: "system",
      });
    }

    const chatEngine = new SimpleChatEngine({ llm });
    const chatResponse = await chatEngine.chat({
      messages: chatHistory,
      stream: true,
    });

    // Create a new ReadableStream
    const stream = new ReadableStream({
      async start(controller) {
        try {
          for await (const chunk of chatResponse) {
            // Extract just the content from the chunk
            const content = chunk.message?.content || "";
            if (content) {
              // Ensure newlines are properly encoded for SSE
              controller.enqueue(content);
            }
          }
          controller.close();
        } catch (error) {
          controller.error(error);
        }
      },
    });

    return new Response(stream, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
      },
    });
  } catch (error) {
    const detail = (error as Error).message;
    return NextResponse.json({ detail }, { status: 500 });
  }
}
