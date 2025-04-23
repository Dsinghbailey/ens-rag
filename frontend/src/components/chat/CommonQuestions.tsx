import { useEffect, useRef } from "react";

const commonQuestions = [
  "What is ENS?",
  "What is a .eth name?",
  "How is ENS different from DNS (like .com)?",
  "Why would I want an ENS name? What are the benefits?",
  "What does it cost to register a .eth domain?",
  "How do I register a new .eth name?",
  "Where is the official place to register and manage ENS names?",
  "Are there gas fees involved in registering or managing ENS names?",
  "How long can I register an ENS name for?",
  "What are ENS records?",
  "How do I set my Ethereum address record for my ENS name?",
  "Can I point my ENS name to other cryptocurrency addresses (like Bitcoin or Solana)? How?",
  "What is a Primary ENS Name (or Reverse Record)? How do I set it?",
  "Why should I set my Primary ENS Name?",
  "How do I add or update text records (like an avatar, email, or website URL)?",
  "How do I set a Content Hash record for a decentralized website (IPFS/Swarm)?",
  "How do I renew my ENS name registration?",
  "What happens if my ENS name expires? Is there a grace period?",
  "How do I transfer my ENS name to a different Ethereum address?",
  "What is the difference between the Registrant and the Controller of an ENS name?",
  "How can I change the Controller address for my name?",
  "How can someone send me crypto using my ENS name?",
  "Which wallets and dApps support ENS?",
  "Can I use my ENS name to log into services?",
  "What are ENS subdomains (e.g., pay.myname.eth)?",
  "How do I create and manage subdomains for my ENS name?",
  "Can I import my existing DNS domain (like .com) into ENS?",
  "What is an ENS Resolver? Do I need to worry about it?",
  "Is ENS only for .eth names?",
];

interface CommonQuestionsProps {
  onQuestionClick: (question: string) => void;
}

export function CommonQuestions({ onQuestionClick }: CommonQuestionsProps) {
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!scrollContainerRef.current) return;

    const scrollContainer = scrollContainerRef.current;
    let animationFrameId: number;
    let scrollPosition = 0;

    const scroll = () => {
      scrollPosition += 0.5;
      if (
        scrollPosition >=
        scrollContainer.scrollWidth - scrollContainer.clientWidth
      ) {
        scrollPosition = 0;
      }

      scrollContainer.scrollLeft = scrollPosition;
      animationFrameId = requestAnimationFrame(scroll);
    };

    animationFrameId = requestAnimationFrame(scroll);

    return () => {
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  return (
    <div className="w-full max-w-3xl mt-6 mb-8 overflow-hidden">
      <div
        ref={scrollContainerRef}
        className="flex gap-3 pb-4 overflow-x-auto whitespace-nowrap scrollbar-none"
        style={{ scrollbarWidth: "none" }}
      >
        {commonQuestions.map((question, index) => (
          <button
            key={index}
            onClick={() => onQuestionClick(question)}
            type="button"
            className="inline-block px-4 py-2 text-black transition-colors bg-gray-100 rounded-full cursor-pointer hover:bg-gray-200 whitespace-nowrap"
          >
            {question}
          </button>
        ))}
      </div>
    </div>
  );
}
