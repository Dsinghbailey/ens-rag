import { useEffect, useRef, useState } from "react";
import { marked } from "marked";
import type { MarkedOptions } from "marked";
import DOMPurify from "dompurify";
import Prism from "prismjs";
import "prismjs/themes/prism-tomorrow.css";
import { Message } from "ai/react";

// Configure marked options
marked.setOptions({
  breaks: true,
  gfm: true,
  langPrefix: "language-",
} as MarkedOptions);

export function MessageList({ messages }: { messages: Message[] }) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messageContainerRef = useRef<HTMLDivElement>(null);
  const [formattedMessages, setFormattedMessages] = useState<
    Record<string, string>
  >({});
  // Add new state to track if we should auto-scroll
  const [shouldAutoScroll, setShouldAutoScroll] = useState(true);
  // Add ref to track last message role
  const lastMessageRole = useRef<string | null>(null);

  // useEffect to log Prism languages
  useEffect(() => {
    console.log("Prism languages", Prism.languages);
  }, []);

  // useEffect to format and pre-highlight messages
  useEffect(() => {
    let isMounted = true; // Handle component unmount during async operation

    const processMessages = async () => {
      const newFormattedMessages: Record<string, string> = {};

      for (const message of messages) {
        if (message.role === "assistant") {
          // Always re-process assistant messages when 'messages' changes,
          // as the content string itself will update during streaming.
          try {
            newFormattedMessages[message.id] = await formatAndHighlightMessage(
              message.content
            );
            // Optional: Log only if debugging is needed
            // console.log(`processMessages: Formatted message ${message.id}`);
          } catch (error) {
            console.error(
              `processMessages: Error formatting message ${message.id}`,
              error
            );
            // Use raw content as fallback ONLY for the specific message that failed
            newFormattedMessages[message.id] = message.content;
          }
        }
        // Note: User messages aren't processed here; they're rendered directly.
      }

      // Update state if the component is still mounted
      if (isMounted) {
        // Let React handle diffing and optimize rendering if the actual HTML hasn't changed
        setFormattedMessages(newFormattedMessages);
      }
    };

    processMessages();

    return () => {
      isMounted = false; // Cleanup function to prevent state update on unmounted component
    };
    // Depend only on the messages array. When its reference changes
    // (new message, stream update), re-run the processing.
  }, [messages]);

  // Add scroll event handler
  useEffect(() => {
    const container = messageContainerRef.current?.parentElement;
    if (!container) return;

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = container;
      // Consider "at bottom" if within 100px of the bottom
      const isAtBottom = scrollHeight - scrollTop - clientHeight < 100;
      setShouldAutoScroll(isAtBottom);
    };

    container.addEventListener("scroll", handleScroll);
    return () => container.removeEventListener("scroll", handleScroll);
  }, []);

  // Modify the scroll effect
  useEffect(() => {
    // Always scroll if it's a new user message
    const isNewUserMessage =
      messages.length > 0 &&
      messages[messages.length - 1].role === "user" &&
      messages[messages.length - 1].role !== lastMessageRole.current;

    if (shouldAutoScroll || isNewUserMessage) {
      messagesEndRef.current?.scrollIntoView({ behavior: "auto" });
    }

    // Update last message role
    lastMessageRole.current =
      messages.length > 0 ? messages[messages.length - 1].role : null;

    const rafId = requestAnimationFrame(() => {
      addCopyButtons();
    });

    return () => {
      cancelAnimationFrame(rafId);
    };
  }, [formattedMessages, messages.length, shouldAutoScroll]);

  // Simplified function to ONLY add copy buttons
  const addCopyButtons = () => {
    if (!messageContainerRef.current) {
      console.log("addCopyButtons: messageContainerRef is null.");
      return;
    }
    console.log("addCopyButtons: Checking for pre elements needing buttons.");

    // Add copy buttons to NEW pre elements
    const pres = messageContainerRef.current.querySelectorAll<HTMLPreElement>(
      'pre[class*="language-"]:not([data-copy-added="true"])' // Target pre tags with language class
    );

    if (pres.length > 0) {
      console.log(
        `addCopyButtons: Found ${pres.length} pre elements to add copy buttons to.`
      );
      pres.forEach((pre) => {
        pre.setAttribute("data-copy-added", "true");
        pre.style.position = "relative";

        const codeElement = pre.querySelector('code[class*="language-"]');
        if (!codeElement) {
          console.warn(
            "addCopyButtons: Found pre tag without a language code block inside, skipping copy button.",
            pre
          );
          return;
        }

        // --- Copy Button Creation and Logic (remains the same) ---
        const copyButton = document.createElement("button");
        copyButton.className =
          "z-10 flex items-center justify-center w-auto h-auto p-1 bg-gray-700 rounded-md cursor-pointer code-copy-button hover:bg-gray-600";
        copyButton.style.position = "absolute";
        copyButton.style.top = "0.5rem";
        copyButton.style.right = "0.5rem";
        copyButton.title = "Copy code";
        copyButton.innerHTML = `
              <span class="copy-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="w-4 h-4 text-gray-300"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg></span>
              <span class="success-icon hidden"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="w-4 h-4 text-gray-300"><polyline points="20 6 9 17 4 12"/></svg></span>
            `;

        copyButton.addEventListener("click", async (e) => {
          e.stopPropagation();
          let codeToCopy = "";
          // Use the actual code element's text content for copying
          codeToCopy = (codeElement.textContent || "").trim();

          if (!codeToCopy) {
            console.error(
              "Failed to extract code to copy from code element:",
              codeElement
            );
            return;
          }

          const copyIcon = copyButton.querySelector(".copy-icon");
          const successIcon = copyButton.querySelector(".success-icon");

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

  // Renamed function: Formats, Sanitizes, AND Highlights
  const formatAndHighlightMessage = async (
    content: string
  ): Promise<string> => {
    console.log("formatAndHighlightMessage: Starting...");
    // 1. Convert Markdown to HTML
    const rawHTML = await marked.parse(content);
    console.log("formatAndHighlightMessage: Marked finished.");

    // 2. Sanitize HTML
    // Allow classes needed by Prism and data attributes
    const sanitizedHTML = DOMPurify.sanitize(rawHTML, {
      ADD_TAGS: ["button", "span", "svg", "path", "rect", "polyline"], // Keep button tags for potential future use
      ADD_ATTR: [
        "class", // Essential for Prism
        "data-prism-highlighted", // Allow our marker
        "data-copy-added", // Allow copy button marker
        "target", // For links
        // Attributes needed for copy button SVGs
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
      ],
    });
    console.log("formatAndHighlightMessage: DOMPurify finished.");

    // 3. Parse sanitized HTML into a temporary DOM structure
    const tempDiv = document.createElement("div");
    tempDiv.innerHTML = sanitizedHTML;

    // 4. Find and Highlight code blocks within the temporary structure
    const codeBlocks = tempDiv.querySelectorAll<HTMLElement>(
      'pre code[class*="language-"]'
    );
    console.log(
      `formatAndHighlightMessage: Found ${codeBlocks.length} code blocks to potentially highlight.`
    );
    codeBlocks.forEach((code) => {
      // Ensure the language class is present (it should be after marked)
      const languageMatch = code.className.match(/language-(\w+)/);
      const language = languageMatch ? languageMatch[1] : null; // Extract language name

      if (language) {
        // Explicitly check if the language grammar is loaded in Prism
        if (Prism.languages[language]) {
          console.log(
            `formatAndHighlightMessage: Language '${language}' grammar found. Attempting highlight.`
          );
          try {
            Prism.highlightElement(code); // Highlight in the temporary DOM
            console.log(
              `formatAndHighlightMessage: Successfully highlighted code block (lang: ${language})`
            );
          } catch (error) {
            console.error(
              `formatAndHighlightMessage: Error during Prism.highlightElement for (lang: ${language})`,
              error,
              code
            );
          }
        } else {
          // Log a warning if the specific language component seems missing
          console.warn(
            `formatAndHighlightMessage: Skipping highlight for code block. Language grammar '${language}' NOT FOUND in Prism.languages. Check component import/loading.`,
            code
          );
        }
      } else {
        console.warn(
          `formatAndHighlightMessage: Skipping highlight for code block, could not extract language from class: ${code.className}`,
          code
        );
      }
    });

    // 5. Add target="_blank" to links (can still do this here)
    const links = tempDiv.querySelectorAll("a");
    links.forEach((link) => {
      link.setAttribute("target", "_blank");
      link.setAttribute("rel", "noopener noreferrer");
    });
    console.log(`formatAndHighlightMessage: Processed ${links.length} links.`);

    // 6. Return the innerHTML of the modified temporary structure
    const finalHTML = tempDiv.innerHTML;
    console.log("formatAndHighlightMessage: Finished, returning final HTML.");
    return finalHTML;
  };

  return (
    <div ref={messageContainerRef} className="w-full py-8">
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
                  [&_pre]:whitespace-pre-wrap
                  [&_pre]:break-words

                  [&_pre_code]:whitespace-pre-wrap
                  [&_pre_code]:word-break-normal
                  [&_pre_code]:text-gray-100

                  [&_code:not(pre_>_code)]:text-sm
                  [&_code:not(pre_>_code)]:bg-gray-900
                  [&_code:not(pre_>_code)]:text-gray-100
                  [&_code:not(pre_>_code)]:px-1
                  [&_code:not(pre_>_code)]:rounded

                  [&_p]:my-3

                  [&_a]:text-blue-600
                  [&_a]:hover:text-blue-800
                  [&_a]:underline
                  [&_a]:transition-colors
                  [&_a]:duration-200
                "
                dangerouslySetInnerHTML={{
                  __html: formattedMessages[message.id] || message.content,
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
