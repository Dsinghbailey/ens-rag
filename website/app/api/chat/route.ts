import { NextRequest, NextResponse } from "next/server";
import { type Message } from "ai";
import { SimpleChatEngine } from "@llamaindex/core/chat-engine";
import { OpenAI } from "@llamaindex/openai";
import type { ChatMessage } from "@llamaindex/core/llms";
const CUSTOMER_PROMPT = "You are trained on ENS documentation.";

const SYSTEM_PROMPT = `
  You are a helpful AI assistant.
  Always format your responses using markdown syntax.
  Be concise.
  Break them into sections when appropriate.
  Use newlines.
  Do not hallucinate.
`;
// Configure the LLM
const llm = new OpenAI({
  model: "gpt-4o-mini",
  temperature: 0.7,
  apiKey: process.env.OPENAI_API_KEY,
});

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

    // Add system message at the beginning of history if not already present
    const chatHistory = [...messages] as ChatMessage[];
    if (chatHistory.length === 0 || chatHistory[0].role !== "system") {
      chatHistory.unshift({
        content: SYSTEM_PROMPT + " " + CUSTOMER_PROMPT,
        role: "system",
      });
    }

    const chatEngine = new SimpleChatEngine({ llm });
    const response = await chatEngine.chat({
      message: userMessage.content,
      chatHistory: chatHistory,
      stream: true,
    });

    // Create a new ReadableStream
    const stream = new ReadableStream({
      async start(controller) {
        for await (const chunk of response) {
          // Extract just the content from the chunk
          const content = chunk.message?.content || "";
          if (content) {
            // Ensure newlines are properly encoded for SSE
            const formattedContent = String(content).replace(/\n/g, "\n");
            controller.enqueue(formattedContent);
          }
        }
        // controller.enqueue(new TextEncoder().encode("data: [DONE]\n\n"));
        controller.close();
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
