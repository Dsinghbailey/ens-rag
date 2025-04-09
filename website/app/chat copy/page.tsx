"use client";

import { Button } from "@/components/ui/button";
import { Send } from "lucide-react";
import Image from "next/image";
import { useState } from "react";

interface Message {
  id: string;
  content: string;
  role: "user" | "assistant";
}

function Messages({ messages }: { messages: Message[] }) {
  return (
    <div className="w-full space-y-4">
      {[...messages].reverse().map((message) => (
        <div
          key={message.id}
          className={`flex ${
            message.role === "user" ? "justify-end" : "justify-start"
          }`}
        >
          <div
            className={`max-w-[80%] py-2 px-3 rounded-lg ${
              message.role === "user"
                ? "bg-stone-100 text-gray-900 "
                : "text-gray-900 "
            }`}
          >
            {message.content}
          </div>
        </div>
      ))}
    </div>
  );
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");

  const handleSend = () => {
    if (!input.trim()) return;

    const newMessage: Message = {
      id: Date.now().toString(),
      content: input.trim(),
      role: "user",
    };

    setMessages((prev) => [newMessage, ...prev]);
    setInput("");
  };

  const hasMessages = messages.length > 0;

  return (
    <main className="min-h-screen bg-white">
      {/* Header with logo */}
      <header className="fixed top-0 left-0 p-4">
        <div className="flex items-center">
          <Image
            src="/ens-logo-Dark_Blue.svg"
            alt="ENS Logo"
            width={80}
            height={80}
          />
        </div>
      </header>

      {/* Main content */}
      <div
        className={`flex flex-col ${
          hasMessages
            ? "min-h-screen"
            : "items-center justify-center min-h-screen"
        } px-4`}
      >
        <div
          className={`max-w-2xl w-full ${
            hasMessages ? "mx-auto pt-16" : "text-center"
          }`}
        >
          <h1 className="text-xl font-bold text-gray-900 tracking-tight sm:text-2xl text-center">
            Chat with ENS Docs
          </h1>

          {/* Messages section */}
          {hasMessages && (
            <div className="mt-8 mb-4">
              <Messages messages={messages} />
            </div>
          )}

          {/* Chat input section */}
          <div
            className={`${
              hasMessages
                ? "fixed bottom-8 left-0 right-0 px-4"
                : "mt-8 relative mb-40"
            }`}
          >
            <div
              className={`${hasMessages ? "max-w-2xl mx-auto relative" : ""}`}
            >
              <textarea
                rows={3}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask a question about ENS..."
                className="w-full px-4 py-2 pr-16 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-orange-500 resize-none"
              />
              <Button
                size="icon"
                className="absolute bottom-4 right-2 h-10 w-10 rounded-full p-0 cursor-pointer"
                disabled={!input.trim()}
                onClick={handleSend}
              >
                <Send className="h-5 w-5" />
              </Button>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
