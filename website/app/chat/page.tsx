"use client";

import { Button } from "@/components/ui/button";
import { Send } from "lucide-react";
import Image from "next/image";
import { useChat, type Message } from "ai/react";
import { useEffect, useRef } from "react";
import { marked } from "marked";
import DOMPurify from "dompurify";
import Prism from "prismjs";
import type { Grammar } from "prismjs";
import "prismjs/themes/prism-tomorrow.css";
import "prismjs/components/prism-javascript";
import "prismjs/components/prism-typescript";
import "prismjs/components/prism-json";
import "prismjs/components/prism-bash";
import "prismjs/plugins/toolbar/prism-toolbar";
import "prismjs/plugins/toolbar/prism-toolbar.css";
import "prismjs/plugins/copy-to-clipboard/prism-copy-to-clipboard";

// Configure marked options
marked.setOptions({
  breaks: true,
  gfm: true,
  // @ts-ignore - highlight is a valid option but not in the types
  highlight: function (code: string, lang: string) {
    if (lang && Prism.languages[lang as keyof typeof Prism.languages]) {
      return Prism.highlight(
        code,
        Prism.languages[lang as keyof typeof Prism.languages] as Grammar,
        lang
      );
    }
    return code;
  },
});

function Messages({ messages }: { messages: Message[] }) {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    // Initialize Prism after content is rendered
    Prism.highlightAll();
  }, [messages]);

  const formatMessage = (content: string) => {
    // Replace multiple newlines with a single newline to prevent excessive spacing
    const normalizedContent = content.replace(/\n{3,}/g, "\n\n");
    const rawHTML = marked.parse(normalizedContent, { async: false });
    return DOMPurify.sanitize(rawHTML);
  };

  return (
    <div className="w-full space-y-4 py-4">
      {messages.map((message) => (
        <div
          key={message.id}
          className={`flex ${
            message.role === "user" ? "justify-end" : "justify-start"
          }`}
        >
          <div
            className={`max-w-[80%] py-2 px-3 rounded-lg ${
              message.role === "user"
                ? "bg-stone-100 text-gray-900"
                : "text-gray-900"
            }`}
          >
            {message.role === "assistant" ? (
              <div
                className="prose prose-sm max-w-none [&_h1]:text-2xl [&_h2]:text-xl [&_h3]:text-lg [&_h4]:text-base [&_pre]:bg-gray-800 [&_pre]:p-4 [&_pre]:rounded-lg [&_pre]:overflow-x-auto [&_code]:text-sm [&_code]:bg-gray-100 [&_.copy-to-clipboard-button]:text-gray-400 [&_.copy-to-clipboard-button]:hover:text-gray-100 [&_.copy-to-clipboard-button]:absolute [&_.copy-to-clipboard-button]:right-2 [&_.copy-to-clipboard-button]:top-2 [&_.copy-to-clipboard-button]:h-8 [&_.copy-to-clipboard-button]:w-8 [&_.copy-to-clipboard-button]:bg-transparent [&_.copy-to-clipboard-button]:border-0 [&_.copy-to-clipboard-button]:cursor-pointer"
                dangerouslySetInnerHTML={{
                  __html: formatMessage(message.content),
                }}
              />
            ) : (
              message.content
            )}
          </div>
        </div>
      ))}
      <div ref={messagesEndRef} />
    </div>
  );
}

export default function ChatPage() {
  const { messages, input, handleInputChange, handleSubmit, isLoading } =
    useChat({
      api: "/api/chat",
      body: {
        customerId: 1,
      },
    });
  const hasMessages = messages.length > 0;

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as unknown as React.FormEvent<HTMLFormElement>);
    }
  };

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
          className={`max-w-3xl w-full ${
            hasMessages ? "mx-auto pt-16" : "text-center"
          }`}
        >
          <h1
            className={`text-xl font-bold text-gray-900 tracking-tight sm:text-2xl text-center ${
              hasMessages ? "border-b border-gray-200 pb-4" : ""
            }`}
          >
            Chat with ENS Docs
          </h1>

          {/* Messages section */}
          {hasMessages && (
            <div className="h-[calc(100vh-200px)] overflow-y-auto">
              <Messages messages={messages} />
            </div>
          )}

          {/* Chat input section */}
          <div
            className={`${
              hasMessages ? "fixed bottom-0 left-0 right-0 px-4" : "mt-8"
            }`}
          >
            <form
              onSubmit={handleSubmit}
              className="max-w-3xl mx-auto relative"
            >
              <textarea
                rows={3}
                value={input}
                onChange={handleInputChange}
                onKeyDown={handleKeyDown}
                placeholder="Ask a question about ENS... "
                className="w-full px-4 py-2 pr-16 border bg-white border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-orange-500 resize-none"
              />
              <Button
                size="icon"
                className="absolute bottom-4 right-2 h-10 w-10 rounded-full p-0 cursor-pointer"
                disabled={!input.trim() || isLoading}
                type="submit"
              >
                <Send className="h-5 w-5" />
              </Button>
            </form>
          </div>
        </div>
      </div>
    </main>
  );
}
