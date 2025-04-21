import { useEffect, useRef } from "react";
import { marked } from "marked";
import DOMPurify from "dompurify";
import Prism from "prismjs";
import type { Grammar } from "prismjs";
import "prismjs/themes/prism-tomorrow.css";
import { type Message } from "ai/react";
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

export function MessageList({ messages }: { messages: Message[] }) {
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
    // add a timeout to run the setupCodeBlocks function again
    setTimeout(() => {
      setupCodeBlocks();
    }, 1000);

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
        "target", // Allow target attribute
      ], // Allow necessary attributes
    });

    // Create a temporary div to parse the HTML
    const tempDiv = document.createElement("div");
    tempDiv.innerHTML = sanitizedHTML;

    // Add target="_blank" to all links
    const links = tempDiv.querySelectorAll("a");
    links.forEach((link) => {
      link.setAttribute("target", "_blank");
      link.setAttribute("rel", "noopener noreferrer");
    });

    // Return the sanitized HTML without the copy button
    return tempDiv.innerHTML;
  };

  return (
    // Remove the onClick handler from the container
    <div ref={messageContainerRef} className="w-full space-y-4 py-8">
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
                  [&_h1]:mt-4
                  [&_h2]:text-xl 
                  [&_h2]:mt-4
                  [&_h3]:text-lg 
                  [&_h3]:mt-3
                  [&_h4]:text-base 
                  [&_h4]:mt-3
       
                  [&_ul]:mb-3
                  [&_ul]:list-disc
                  [&_ul]:pl-5
                  
                  [&_pre]:bg-gray-800 
                  [&_pre]:p-4 
                  [&_pre]:rounded-lg 
                  [&_pre]:overflow-x-auto 
                  [&_pre]:mb-4
                  
                  [&_pre_code]:text-sm 
                  [&_pre_code]:text-gray-100
                  
                  [&_code]:text-sm 
                  [&_code]:bg-gray-900 
                  [&_code]:text-gray-100 
                  [&_code]:px-1 
                  [&_code]:rounded 
                  
                  [&_p]:my-3
             

                  [&_a]:text-blue-600
                  [&_a]:hover:text-blue-800
                  [&_a]:underline
                  [&_a]:transition-colors
                  [&_a]:duration-200
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
