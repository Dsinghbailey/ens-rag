import { Button } from "../ui/Button";
import { Send } from "lucide-react";

interface ChatInputProps {
  className?: string;
  input: string;
  handleInputChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void;
  handleSubmit: (e: React.FormEvent<HTMLFormElement>) => void;
  status: "submitted" | "streaming" | "ready" | "error";
}

export function ChatInput({
  className = "",
  input,
  handleInputChange,
  handleSubmit,
  status,
}: ChatInputProps) {
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as unknown as React.FormEvent<HTMLFormElement>);
    }
  };

  const isLoading = status === "submitted" || status === "streaming";

  return (
    <form onSubmit={handleSubmit} className={`relative ${className}`}>
      <textarea
        rows={3}
        value={input}
        onChange={handleInputChange}
        onKeyDown={handleKeyDown}
        placeholder="Ask a question about ENS... "
        className="w-full px-4 py-2 pr-16 border bg-white border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
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
  );
}
