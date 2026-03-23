"use client";

/**
 * Individual chat message bubble.
 *
 * User messages: right-aligned with store primary colour background.
 * Assistant messages: left-aligned, white background.
 *
 * Features:
 *   - Blinking cursor (▋) on the active streaming message
 *   - Confidence indicator dot after streaming completes (green / amber / red)
 *   - Source tag chips below assistant messages
 *   - Timestamp display
 */

import type { ChatMessage, ChatMetadata } from "../lib/types";

interface MessageBubbleProps {
  message: ChatMessage;
  primaryColor: string;
  /** True only on the last assistant message while the stream is active */
  isStreamingThis?: boolean;
  /** Populated after the stream for the last assistant message */
  metadata?: ChatMetadata | null;
}

function ConfidenceDot({ confidence }: { confidence: number }) {
  const color =
    confidence >= 0.8
      ? "bg-green-400"
      : confidence >= 0.65
      ? "bg-amber-400"
      : "bg-red-400";
  const label =
    confidence >= 0.8
      ? "High confidence"
      : confidence >= 0.65
      ? "Medium confidence"
      : "Low confidence";

  return (
    <span
      className={`inline-block w-2 h-2 rounded-full ${color} shrink-0 mt-1`}
      title={`${label} (${(confidence * 100).toFixed(0)}%)`}
      aria-label={label}
    />
  );
}

function formatTime(timestamp: number): string {
  return new Date(timestamp).toLocaleTimeString("en-AU", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function MessageBubble({
  message,
  primaryColor,
  isStreamingThis = false,
  metadata,
}: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} px-1`}>
      <div className={`max-w-[78%] space-y-1 ${isUser ? "items-end" : "items-start"} flex flex-col`}>
        {/* Bubble */}
        <div
          className={`rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm ${
            isUser
              ? "text-white rounded-br-sm"
              : "bg-white text-gray-800 border border-gray-100 rounded-bl-sm"
          }`}
          style={isUser ? { backgroundColor: primaryColor } : undefined}
        >
          {message.content ? (
            <span>
              {message.content}
              {isStreamingThis && (
                <span
                  className="inline-block w-[2px] h-[1em] ml-0.5 align-middle animate-blink"
                  aria-hidden="true"
                  style={{ backgroundColor: isUser ? "white" : "#374151" }}
                />
              )}
            </span>
          ) : isStreamingThis ? (
            <span className="flex gap-1 items-center py-0.5">
              <span className="w-2 h-2 rounded-full bg-gray-300 animate-bounce [animation-delay:0ms]" />
              <span className="w-2 h-2 rounded-full bg-gray-300 animate-bounce [animation-delay:150ms]" />
              <span className="w-2 h-2 rounded-full bg-gray-300 animate-bounce [animation-delay:300ms]" />
            </span>
          ) : (
            <span className="text-gray-300 italic">Empty</span>
          )}
        </div>

        {/* Metadata row (assistant only, after streaming) */}
        {!isUser && !isStreamingThis && metadata && (
          <div className="flex items-start gap-2 px-1">
            <ConfidenceDot confidence={metadata.confidence} />
            <div className="flex flex-wrap gap-1">
              {metadata.sources.slice(0, 4).map((src, i) => {
                const label = src.includes(":")
                  ? src.split(":")[0]
                  : src;
                const capitalised =
                  label.charAt(0).toUpperCase() + label.slice(1);
                return (
                  <span
                    key={i}
                    className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-gray-100 text-gray-500"
                  >
                    {capitalised}
                  </span>
                );
              })}
            </div>
          </div>
        )}

        {/* Timestamp */}
        <span className="text-[10px] text-gray-300 px-1">
          {formatTime(message.timestamp)}
        </span>
      </div>
    </div>
  );
}
