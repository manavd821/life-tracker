"use client";

import { useEffect, useRef, useState } from "react";
import { Loader2, Send, Sparkles } from "lucide-react";

import { askLifeTrackerAI } from "@/app/actions";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import type { ChatMessage } from "@/lib/backend";

const SUGGESTIONS = [
  "Why was my task completion low?",
  "Where did I spend most of my time?",
  "What patterns did you notice?",
  "How did my study time look today?",
  "What could I experiment with tomorrow?",
];

// Only the most recent messages are sent to the backend per request.
const MAX_HISTORY = 10;

const FALLBACK_ERROR =
  "I couldn't generate a response right now. Your recorded data is still available.";

type Props = {
  date: string;
  tzOffsetMinutes: number;
};

export function AiChat({ date, tzOffsetMinutes }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const element = scrollRef.current;
    if (element) element.scrollTop = element.scrollHeight;
  }, [messages, pending, error]);

  async function send(text: string) {
    const message = text.trim();
    if (!message || pending) return;

    const history = messages.slice(-MAX_HISTORY);
    setInput("");
    setError(null);
    setPending(true);
    setMessages((previous) => [...previous, { role: "user", content: message }]);

    try {
      const result = await askLifeTrackerAI(message, date, tzOffsetMinutes, history);
      if (result.ok) {
        setMessages((previous) => [
          ...previous,
          { role: "assistant", content: result.reply },
        ]);
      } else {
        setError(result.message);
      }
    } catch {
      setError(FALLBACK_ERROR);
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="flex flex-col gap-4">
      <h2 className="text-sm font-medium tracking-wide text-muted-foreground uppercase">
        Ask about your behavior
      </h2>

      <div className="flex flex-col gap-4 rounded-lg border border-border px-4 py-4">
        <div className="flex items-center gap-2 text-sm">
          <Sparkles className="size-4 text-muted-foreground" />
          <span className="font-medium">Life Tracker AI</span>
          <span className="text-xs text-muted-foreground">· {date}</span>
        </div>

        <div
          ref={scrollRef}
          className="flex max-h-80 min-h-24 flex-col gap-3 overflow-y-auto pr-1"
        >
          {messages.length === 0 && !pending && !error ? (
            <div className="flex flex-col gap-2">
              <p className="text-sm text-muted-foreground">
                Answers are built from your recorded behaviors, tasks, and
                detected patterns for this date.
              </p>
              <div className="flex flex-wrap gap-2">
                {SUGGESTIONS.map((suggestion) => (
                  <Button
                    key={suggestion}
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => void send(suggestion)}
                  >
                    {suggestion}
                  </Button>
                ))}
              </div>
            </div>
          ) : null}

          {messages.map((entry, index) => (
            <MessageBubble key={index} entry={entry} />
          ))}

          {pending ? (
            <p className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="size-4 animate-spin" />
              Sending...
            </p>
          ) : null}
        </div>

        {error ? (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        ) : null}

        <form
          onSubmit={(event) => {
            event.preventDefault();
            void send(input);
          }}
          className="flex items-end gap-2"
        >
          <Textarea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void send(input);
              }
            }}
            placeholder="Type your question..."
            rows={1}
            className="max-h-32 resize-none"
            disabled={pending}
          />
          <Button
            type="submit"
            size="icon"
            disabled={pending || input.trim() === ""}
            aria-label="Send message"
          >
            <Send className="size-4" />
          </Button>
        </form>
      </div>
    </section>
  );
}

function MessageBubble({ entry }: { entry: ChatMessage }) {
  const isUser = entry.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] rounded-lg px-3 py-2 text-sm whitespace-pre-wrap ${
          isUser
            ? "bg-secondary text-secondary-foreground"
            : "border border-border bg-card text-foreground"
        }`}
      >
        <span className="mb-1 block text-[10px] tracking-wide text-muted-foreground uppercase">
          {isUser ? "You" : "AI"}
        </span>
        {entry.content}
      </div>
    </div>
  );
}
