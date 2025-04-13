"use client";

import Image from "next/image";
import { useChat, Message } from "ai/react";
import { Info } from "lucide-react";
import { ChatInput } from "@/components/chat/ChatInput";
import { MessageList } from "@/components/chat/MessageList";
import { useState, useEffect, useCallback } from "react";
import { CommonQuestions } from "@/components/chat/CommonQuestions";

export default function ChatPage() {
  const [loadingMessage, setLoadingMessage] = useState("Looking up sources...");
  const [isStreaming, setIsStreaming] = useState(false);
  const [questionToSubmit, setQuestionToSubmit] = useState<string | null>(null);
  const [isTooltipVisible, setIsTooltipVisible] = useState(false);

  const {
    messages,
    input,
    handleInputChange,
    handleSubmit,
    isLoading,
    append,
  } = useChat({
    api: "http://localhost:3001/chat",
    body: {
      customerId: 1,
    },
    headers: {
      "Content-Type": "application/json",
    },
    onResponse: () => {
      setIsStreaming(true);
    },
    onFinish: () => {
      setIsStreaming(false);
    },
  });
  const hasMessages = messages.length > 0;

  useEffect(() => {
    if (!isLoading) return;

    const messages = [
      "Looking up sources...",
      "Getting relevant chunks...",
      "Creating answer...",
    ];
    let currentIndex = 0;

    const interval = setInterval(() => {
      currentIndex = (currentIndex + 1) % messages.length;
      setLoadingMessage(messages[currentIndex]);
    }, 2000); // Change message every 2 seconds

    return () => clearInterval(interval);
  }, [isLoading]);

  useEffect(() => {
    if (questionToSubmit) {
      const messageToAppend: Omit<Message, "id"> = {
        role: "user",
        content: questionToSubmit,
      };
      append(messageToAppend);
      setQuestionToSubmit(null);
    }
  }, [questionToSubmit, append]);

  const handleCommonQuestionClick = useCallback((question: string) => {
    setQuestionToSubmit(question);
  }, []);

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
          className={`max-w-3xl w-full ${hasMessages ? "mx-auto pt-12" : ""}`}
        >
          {/* Added flex wrapper to center the title+icon block */}
          <div className="flex justify-center w-full">
            <div className="relative w-full max-w-3xl">
              <div
                className={`flex items-center justify-center w-full ${
                  hasMessages ? "border-b border-gray-200 pb-4" : ""
                }`}
              >
                <h1 className="text-xl font-bold text-gray-900 tracking-tight sm:text-2xl">
                  Chat with ENS Docs
                </h1>
                <div className="relative group ml-2">
                  <Info
                    className="w-5 h-5 text-gray-500 cursor-pointer"
                    onClick={() => setIsTooltipVisible(true)}
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Messages section */}
          {hasMessages && (
            <div className="h-[calc(100vh-200px)] overflow-y-auto">
              <MessageList messages={messages} />
              {isLoading && !isStreaming && (
                <div className="flex gap-3 pb-4 mb-8 w-full">
                  <div className="flex-1">
                    <p className="italic text-gray-600">{loadingMessage}</p>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Chat input section */}
          <div
            className={`${
              hasMessages ? "fixed bottom-4 left-0 right-0 px-4" : "mt-6"
            }`}
          >
            <ChatInput
              className="max-w-3xl mx-auto relative"
              input={input}
              handleInputChange={handleInputChange}
              handleSubmit={handleSubmit}
              isLoading={isLoading}
            />
          </div>
          {/* Common Questions Section - Pass the memoized state setter */}
          {!hasMessages && (
            <CommonQuestions onQuestionClick={handleCommonQuestionClick} />
          )}
        </div>
      </div>

      {/* Modal */}
      {isTooltipVisible && (
        <div
          className="fixed inset-0 bg-black/30 z-50 flex items-center justify-center"
          onClick={() => setIsTooltipVisible(false)}
        >
          <div
            className="bg-white rounded-lg p-6 max-w-sm w-full mx-4 relative"
            onClick={(e) => e.stopPropagation()}
          >
            Trained on the following repositories:
            <ul className="list-disc pl-4 my-2">
              <li>
                <a
                  href="https://github.com/ensdomains/docs"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="underline hover:text-blue-300"
                >
                  ensdomains/docs
                </a>
              </li>
              <li>
                <a
                  href="https://github.com/ensdomains/ensips"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="underline hover:text-blue-300"
                >
                  ensdomains/ensips
                </a>
              </li>
              <li>
                <a
                  href="https://github.com/ensdomains/ens-support-docs"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="underline hover:text-blue-300"
                >
                  ensdomains/ens-support-docs
                </a>
              </li>
            </ul>
            Answers may be inaccurate.
          </div>
        </div>
      )}
    </main>
  );
}
