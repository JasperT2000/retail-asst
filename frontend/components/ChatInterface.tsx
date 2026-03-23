"use client";

/**
 * Chat column component — streaming conversation with the RAG pipeline.
 *
 * Manages message state via Zustand. Cancels the SSE stream via AbortController
 * when the component unmounts. Emits voice output after each assistant response
 * via the VoiceOutput component.
 *
 * Props:
 *   storeSlug      — active store (used for store context + Zustand switch)
 *   primaryColor   — accent colour from the store theme
 *   prefillMessage — pre-populate the input (from knowledge panel click)
 *   onPrefillConsumed — clear prefill in parent after it is consumed
 */

import {
  useState,
  useRef,
  useEffect,
  useCallback,
  KeyboardEvent,
} from "react";
import { Send, Trash2 } from "lucide-react";
import MessageBubble from "./MessageBubble";
import HumanHandoff from "./HumanHandoff";
import VoiceInput from "./VoiceInput";
import VoiceOutput from "./VoiceOutput";
import { streamChat } from "../lib/sse";
import { useAppStore } from "../lib/store";
import type { ChatMessage } from "../lib/types";
import { STORE_NAMES } from "../lib/types";

/** Strip markdown formatting so TTS reads clean natural prose. */
function stripMarkdownForTTS(text: string): string {
  return text
    .replace(/\*\*(.*?)\*\*/g, "$1")      // **bold** → bold
    .replace(/\*(.*?)\*/g, "$1")           // *italic* → italic
    .replace(/`{1,3}[^`]*`{1,3}/g, "")    // `code` / ```blocks``` → removed
    .replace(/^#{1,6}\s+/gm, "")          // # Headings → plain text
    .replace(/^[-*]\s+/gm, "")            // - bullet / * bullet → removed
    .replace(/^\d+\.\s+/gm, "")           // 1. numbered list → removed
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1") // [link](url) → link text only
    .replace(/\n{2,}/g, ". ")             // paragraph breaks → pause
    .replace(/\n/g, " ")                  // single newlines → space
    .replace(/\s{2,}/g, " ")              // collapse extra spaces
    .trim();
}

const WELCOME_MESSAGES: Record<string, string> = {
  jbhifi:
    "G'day! Welcome to JB Hi-Fi. 👋 I'm your AI store assistant — I can help you find products, check live stock levels, locate aisle and bay numbers, compare prices, and navigate store policies. Powered by a hybrid AI pipeline combining a knowledge graph with vector search. What are you after today?",
  bunnings:
    "G'day! Welcome to Bunnings Warehouse. 👋 I'm your AI store assistant — here to help you find the right product for any project, check stock, pinpoint aisle locations, and understand store policies. What are you working on today?",
  babybunting:
    "G'day! Welcome to Baby Bunting. 👋 I'm your AI store assistant — ready to help you find the perfect products for your little one, check availability, locate items in-store, and answer questions about our policies and services. How can I help?",
  supercheapauto:
    "G'day! Welcome to Supercheap Auto. 👋 I'm your AI store assistant — I can help you find parts, tools, and accessories, check stock levels, locate items in-store, and clarify store policies. What are you working on?",
};

interface ChatInterfaceProps {
  storeSlug: string;
  primaryColor: string;
  prefillMessage?: string;
  onPrefillConsumed?: () => void;
}

export default function ChatInterface({
  storeSlug,
  primaryColor,
  prefillMessage,
  onPrefillConsumed,
}: ChatInterfaceProps) {
  const {
    chatHistory,
    isStreaming,
    streamMetadata,
    humanNotified,
    sessionId,
    setCurrentStore,
    addMessage,
    appendToLastMessage,
    setStreaming,
    setMetadata,
    setHumanNotified,
    clearHistory,
  } = useAppStore();

  const [input, setInput] = useState("");
  const [speakText, setSpeakText] = useState("");
  const [speakTrigger, setSpeakTrigger] = useState(0);

  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Switch store context (clears chat history if slug changed)
  useEffect(() => {
    setCurrentStore(storeSlug);
  }, [storeSlug, setCurrentStore]);

  // Seed welcome message when store loads (or changes) and history is empty
  useEffect(() => {
    const { chatHistory: h } = useAppStore.getState();
    if (h.length === 0) {
      const welcomeText =
        WELCOME_MESSAGES[storeSlug] ??
        `G'day! Welcome to ${STORE_NAMES[storeSlug] ?? "the store"}. How can I help you today?`;
      addMessage({
        role: "assistant",
        content: welcomeText,
        timestamp: Date.now(),
      });
    }
  }, [storeSlug, addMessage]);

  // Consume prefill from knowledge panel
  useEffect(() => {
    if (prefillMessage) {
      setInput(prefillMessage);
      inputRef.current?.focus();
      onPrefillConsumed?.();
    }
  }, [prefillMessage, onPrefillConsumed]);

  // Auto-scroll on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory]);

  // Cancel stream on unmount
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || isStreaming) return;

      // Cancel any in-flight stream
      abortRef.current?.abort();
      abortRef.current = new AbortController();

      const userMsg: ChatMessage = {
        role: "user",
        content: text,
        timestamp: Date.now(),
      };
      addMessage(userMsg);
      setInput("");
      setStreaming(true);
      setHumanNotified(false);
      setMetadata(null);

      // Placeholder for the incoming assistant response
      addMessage({ role: "assistant", content: "", timestamp: Date.now() });

      // History for the API (exclude the empty placeholder we just added)
      const historyForApi = chatHistory
        .filter((m) => m.content.trim())
        .map((m) => ({ role: m.role, content: m.content }));

      await streamChat(
        storeSlug,
        text,
        sessionId,
        historyForApi,
        {
          onToken: (token) => appendToLastMessage(token),
          onMetadata: (meta) => {
            setMetadata(meta);
            if (meta.human_notified) setHumanNotified(true);
          },
          onDone: () => {
            setStreaming(false);
            // Trigger TTS for the completed response — strip markdown first
            const { chatHistory: h } = useAppStore.getState();
            const lastContent = h.at(-1)?.content ?? "";
            if (lastContent) {
              setSpeakText(stripMarkdownForTTS(lastContent));
              setSpeakTrigger((n) => n + 1);
            }
          },
          onError: () => {
            // Replace the empty assistant placeholder with an error message
            const { updateLastMessage } = useAppStore.getState();
            updateLastMessage(
              "Sorry, something went wrong. Please try again."
            );
            setStreaming(false);
          },
        },
        abortRef.current.signal
      );
    },
    [
      storeSlug,
      sessionId,
      chatHistory,
      isStreaming,
      addMessage,
      appendToLastMessage,
      setStreaming,
      setMetadata,
      setHumanNotified,
    ]
  );

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  const isEmpty = chatHistory.length === 0;

  return (
    <div className="flex flex-col h-full bg-gray-50">
      {/* Human handoff banner */}
      {humanNotified && <HumanHandoff />}

      {/* Message thread */}
      <div className="flex-1 overflow-y-auto py-6 px-4 space-y-4 scrollbar-thin">
        {isEmpty && (
          <div className="flex flex-col items-center justify-center h-full text-center py-16 space-y-3">
            <div className="w-14 h-14 rounded-full flex items-center justify-center text-2xl"
              style={{ backgroundColor: `${primaryColor}20` }}>
              💬
            </div>
            <p className="text-gray-400 text-sm max-w-xs leading-relaxed">
              Ask me anything about products, prices, aisle locations, or store
              policies.
            </p>
          </div>
        )}

        {chatHistory.map((msg, i) => {
          const isLastAssistant =
            msg.role === "assistant" && i === chatHistory.length - 1;
          return (
            <MessageBubble
              key={i}
              message={msg}
              primaryColor={primaryColor}
              isStreamingThis={isLastAssistant && isStreaming}
              metadata={
                isLastAssistant && !isStreaming ? streamMetadata : null
              }
            />
          );
        })}

        <div ref={bottomRef} />
      </div>

      {/* Input area */}
      <div className="border-t border-gray-200 bg-white px-4 py-3">
        <div className="flex items-center gap-2">
          <VoiceInput
            onTranscript={(text) => setInput(text)}
            onSubmit={(text) => sendMessage(text)}
            disabled={isStreaming}
            autoSubmit
          />
          <VoiceOutput speakText={speakText} speakTrigger={speakTrigger} />

          <input
            ref={inputRef}
            type="text"
            className="flex-1 rounded-full border border-gray-300 bg-white px-4 py-2.5 text-sm outline-none transition-shadow focus:ring-2 focus:border-transparent disabled:bg-gray-50 disabled:text-gray-400"
            style={{
              ["--tw-ring-color" as string]: primaryColor,
            }}
            placeholder="Type your question…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isStreaming}
            maxLength={500}
            aria-label="Chat input"
          />

          <button
            type="button"
            onClick={() => sendMessage(input)}
            disabled={isStreaming || !input.trim()}
            className="rounded-full p-2.5 text-white transition-all disabled:opacity-40 disabled:cursor-not-allowed hover:opacity-90 active:scale-95"
            style={{ backgroundColor: primaryColor }}
            aria-label="Send message"
          >
            <Send className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>

        {/* Footer: session ID + clear button */}
        <div className="flex items-center justify-between mt-2 px-1">
          <span
            className="text-[10px] text-gray-300 font-mono"
            title="Session ID — useful for tracing in Langfuse"
          >
            {sessionId.slice(0, 8)}…
          </span>
          {!isEmpty && (
            <button
              type="button"
              onClick={clearHistory}
              className="flex items-center gap-1 text-[10px] text-gray-300 hover:text-gray-500 transition-colors"
              aria-label="Clear chat history"
            >
              <Trash2 className="h-3 w-3" aria-hidden="true" />
              Clear
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
