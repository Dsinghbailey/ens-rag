"use client";

import { Button } from "@/components/ui/button";
import { Send, Copy, Check } from "lucide-react";
import Image from "next/image";
import { useChat, type Message } from "ai/react";
import { useEffect, useRef } from "react";
import { marked } from "marked";
import DOMPurify from "dompurify";
import Prism from "prismjs";
import type { Grammar } from "prismjs";
import "prismjs/themes/prism-tomorrow.css";

// Core languages - load these first
import "prismjs/components/prism-core";
import "prismjs/components/prism-clike";
import "prismjs/components/prism-markup";
import "prismjs/components/prism-c";
import "prismjs/components/prism-cpp";
import "prismjs/components/prism-javascript";
import "prismjs/components/prism-typescript";
import "prismjs/components/prism-jsx";
import "prismjs/components/prism-tsx";
import "prismjs/components/prism-css";
import "prismjs/components/prism-scss";
import "prismjs/components/prism-less";
import "prismjs/components/prism-stylus";
import "prismjs/components/prism-json";
import "prismjs/components/prism-bash";
import "prismjs/components/prism-python";
import "prismjs/components/prism-rust";
import "prismjs/components/prism-solidity";
import "prismjs/components/prism-java";
import "prismjs/components/prism-go";
import "prismjs/components/prism-ruby";
import "prismjs/components/prism-php";
import "prismjs/components/prism-sql";
import "prismjs/components/prism-markdown";
import "prismjs/components/prism-yaml";
import "prismjs/components/prism-toml";
import "prismjs/components/prism-docker";
import "prismjs/components/prism-git";
import "prismjs/components/prism-diff";
import "prismjs/components/prism-regex";
import "prismjs/components/prism-graphql";
import "prismjs/components/prism-protobuf";

// Configure marked options
marked.setOptions({
  breaks: true,
  gfm: true,
  // @ts-ignore - highlight is a valid option but not in the types
  highlight: function (code: string, lang: string) {
    if (lang && Prism.languages[lang as keyof typeof Prism.languages]) {
      try {
        // Special handling for Solidity
        if (lang === "solidity") {
          return Prism.highlight(
            code,
            Prism.languages.solidity as Grammar,
            "solidity"
          );
        }
        return Prism.highlight(
          code,
          Prism.languages[lang as keyof typeof Prism.languages] as Grammar,
          lang
        );
      } catch (error) {
        console.warn(`Failed to highlight code for language: ${lang}`, error);
        return code;
      }
    }
    return code;
  },
});

function Messages({ messages }: { messages: Message[] }) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messageContainerRef = useRef<HTMLDivElement>(null); // Ref for the container

  const setupCodeBlocks = () => {
    if (messageContainerRef.current) {
      Prism.highlightAllUnder(messageContainerRef.current);

      // Add copy buttons
      const pres = messageContainerRef.current.querySelectorAll<HTMLPreElement>(
        'pre:not([data-copy-added="true"])'
      );

      pres.forEach((pre) => {
        pre.setAttribute("data-copy-added", "true"); // Mark as processed
        pre.style.position = "relative";

        const copyButton = document.createElement("button");
        copyButton.className =
          "code-copy-button absolute top-2 right-2 p-1 rounded-md bg-gray-700 hover:bg-gray-600 cursor-pointer flex items-center justify-center w-auto h-auto"; // Added flex styles
        copyButton.title = "Copy code";
        copyButton.innerHTML = `
              <span class="copy-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="w-4 h-4 text-gray-300"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg></span>
              <span class="success-icon hidden"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="w-4 h-4 text-gray-300"><polyline points="20 6 9 17 4 12"/></svg></span>
            `;

        copyButton.addEventListener("click", async (e) => {
          e.stopPropagation();

          // --- Robust Code Extraction Start ---
          const codeElement = pre.querySelector("code");
          let codeToCopy = "";
          const nodeToClone = codeElement || pre;
          const clone = nodeToClone.cloneNode(true) as HTMLElement;
          const buttonInClone = clone.querySelector(".code-copy-button");
          if (buttonInClone) {
            buttonInClone.remove();
          }
          // If we cloned the pre, try to get text only from a code element inside if it exists
          const codeInClone = clone.querySelector("code");
          codeToCopy = codeInClone
            ? codeInClone.textContent || ""
            : clone.textContent || "";
          codeToCopy = codeToCopy.trim();
          // --- Robust Code Extraction End ---

          if (!codeToCopy) {
            console.error("Failed to extract code to copy from pre:", pre);
            return;
          }

          const copyIcon = copyButton.querySelector(".copy-icon");
          const successIcon = copyButton.querySelector(".success-icon");

          // copy to clipboard check
          try {
            await navigator.clipboard.writeText(codeToCopy);
            if (copyIcon && successIcon) {
              copyIcon.classList.add("hidden");
              successIcon.classList.remove("hidden");
              setTimeout(() => {
                copyIcon.classList.remove("hidden");
                successIcon.classList.add("hidden");
              }, 1000);
            }
          } catch (err) {
            console.error("Failed to copy code:", err);
          }
        });
        pre.appendChild(copyButton);
      });
    }
  };

  // Main effect for scrolling and highlighting
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });

    // First pass at highlighting
    setupCodeBlocks();

    // Schedule a second pass after the browser has rendered
    const animationFrameId = requestAnimationFrame(() => {
      setupCodeBlocks();
    });

    return () => cancelAnimationFrame(animationFrameId);
  }, [messages]); // Re-run when messages change

  const formatMessage = (content: string) => {
    const rawHTML = marked.parse(content, { async: false });
    const sanitizedHTML = DOMPurify.sanitize(rawHTML, {
      ADD_TAGS: ["button", "span", "svg", "path", "rect", "polyline"], // Allow button elements
      ADD_ATTR: [
        "class",
        "width",
        "height",
        "viewBox",
        "fill",
        "stroke",
        "stroke-width",
        "stroke-linecap",
        "stroke-linejoin",
        "points",
        "x",
        "y",
        "rx",
        "ry",
        "d",
      ], // Allow necessary attributes
    });

    // Create a temporary div to parse the HTML
    const tempDiv = document.createElement("div");
    tempDiv.innerHTML = sanitizedHTML;

    // Return the sanitized HTML without the copy button
    return tempDiv.innerHTML;
  };

  return (
    // Remove the onClick handler from the container
    <div ref={messageContainerRef} className="w-full space-y-4 py-4">
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
                className="prose prose-sm max-w-none
                  [&_h1]:text-2xl 
                  [&_h2]:text-xl 
                  [&_h3]:text-lg 
                  [&_h4]:text-base 
                  
                  [&_pre]:bg-gray-800 
                  [&_pre]:p-4 
                  [&_pre]:rounded-lg 
                  [&_pre]:overflow-x-auto 
                  
                  [&_pre_code]:text-sm 
                  [&_pre_code]:text-gray-100
                  
                  [&_code]:text-sm 
                  [&_code]:text-gray-900 
                  [&_code]:bg-gray-100 
                  [&_code]:px-1 
                  [&_code]:rounded 
                  
              "
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
              hasMessages ? "fixed bottom-4 left-0 right-0 px-4" : "mt-8"
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
