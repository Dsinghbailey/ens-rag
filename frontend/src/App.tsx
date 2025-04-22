import { useState, useEffect, useCallback } from "react";
import { useChat } from "@ai-sdk/react";
import { type Message } from "@ai-sdk/react";
import { Info } from "lucide-react";
import { ChatInput } from "./components/chat/ChatInput";
import { MessageList } from "./components/chat/MessageList";
import { CommonQuestions } from "./components/chat/CommonQuestions";
import logo from "./assets/ens-logo-Dark_Blue.svg";

export default function ChatPage() {
  const [loadingMessage, setLoadingMessage] = useState("Looking up sources...");
  const [isStreaming, setIsStreaming] = useState(false);
  const [questionToSubmit, setQuestionToSubmit] = useState<string | null>(null);
  const [isTooltipVisible, setIsTooltipVisible] = useState(false);

  const { messages, input, handleInputChange, handleSubmit, status, append } =
    useChat({
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
      onError: (error) => {
        console.error("Error:", error);
      },
      streamProtocol: "text",
    });
  const hasMessages = messages.length > 0;
  const isLoading = status === "submitted";

  // UseEffect to change loading message
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
    }, 1500); // Change message every 1.5 seconds

    return () => clearInterval(interval);
  }, [isLoading]);

  // UseEffect to append user message
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
          <img src={logo} alt="ENS Logo" width={80} height={80} />
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
                <h1 className="text-xl font-bold tracking-tight text-gray-900 sm:text-2xl">
                  Chat with ENS Docs
                </h1>
                <div className="relative ml-2 group">
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
                <div className="flex w-full gap-3 pb-4 mb-8">
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
              className="relative max-w-3xl mx-auto"
              input={input}
              handleInputChange={handleInputChange}
              handleSubmit={handleSubmit}
              status={status}
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
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
          onClick={() => setIsTooltipVisible(false)}
        >
          <div
            className="relative w-full max-w-sm p-6 mx-4 bg-white rounded-lg"
            onClick={(e) => e.stopPropagation()}
          >
            Trained on the following repositories:
            <ul className="pl-4 my-2 list-disc">
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
