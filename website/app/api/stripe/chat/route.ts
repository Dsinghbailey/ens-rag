import { NextRequest, NextResponse } from "next/server";
import { LlamaIndexAdapter, type Message } from "ai";
import { SimpleChatEngine } from "@llamaindex/core/chat-engine";
import { OpenAI } from "@llamaindex/openai";
import type { ChatMessage } from "@llamaindex/core/llms";

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

    const chatEngine = new SimpleChatEngine({ llm });

    return LlamaIndexAdapter.toDataStreamResponse(
      await chatEngine.chat({
        message: userMessage.content,
        chatHistory: messages as ChatMessage[],
        stream: true,
      }),
      {}
    );
  } catch (error) {
    const detail = (error as Error).message;
    return NextResponse.json({ detail }, { status: 500 });
  }
}
