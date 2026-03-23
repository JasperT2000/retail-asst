/**
 * Server-Sent Events stream handler for the chat endpoint.
 *
 * Connects to POST /chat/stream using the Fetch API with a ReadableStream
 * body reader. Parses SSE event/data pairs and dispatches to callbacks.
 *
 * Pass an AbortSignal to cleanly cancel the stream when the component
 * unmounts (prevents state updates on unmounted components).
 *
 * Auto-reconnect: on transient network errors the stream is retried up to
 * MAX_RETRIES times before calling onError.
 */

import type { ChatMetadata, ConversationMessage } from "./types";

const BASE_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

const MAX_RETRIES = 2;

export interface SSECallbacks {
  onToken: (token: string) => void;
  onMetadata: (metadata: ChatMetadata) => void;
  onDone: () => void;
  onError: (error: string) => void;
}

export async function streamChat(
  storeSlug: string,
  message: string,
  sessionId: string,
  conversationHistory: ConversationMessage[],
  callbacks: SSECallbacks,
  signal?: AbortSignal
): Promise<void> {
  let attempt = 0;

  while (attempt <= MAX_RETRIES) {
    if (signal?.aborted) return;

    try {
      const response = await fetch(`${BASE_URL}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          store_slug: storeSlug,
          message,
          session_id: sessionId,
          conversation_history: conversationHistory,
        }),
        signal,
      });

      if (!response.ok) {
        // 4xx errors are not retryable
        if (response.status >= 400 && response.status < 500) {
          callbacks.onError(`Request error ${response.status}`);
          return;
        }
        throw new Error(`HTTP ${response.status}`);
      }

      if (!response.body) {
        callbacks.onError("No response body");
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let eventType = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith("data: ")) {
            const dataStr = line.slice(6).trim();
            try {
              const data = JSON.parse(dataStr) as Record<string, unknown>;
              if (eventType === "token" && typeof data.token === "string") {
                callbacks.onToken(data.token);
              } else if (eventType === "metadata") {
                callbacks.onMetadata(data as unknown as ChatMetadata);
              } else if (eventType === "done") {
                callbacks.onDone();
              } else if (eventType === "error") {
                const msg =
                  typeof data.message === "string"
                    ? data.message
                    : "Unknown error";
                callbacks.onError(msg);
              }
            } catch {
              // Ignore malformed data lines
            }
            eventType = "";
          }
        }
      }

      // Stream completed successfully — no need to retry
      return;
    } catch (err) {
      if (signal?.aborted) return; // Clean cancellation, not an error

      attempt++;
      if (attempt > MAX_RETRIES) {
        const msg = err instanceof Error ? err.message : "Stream failed";
        callbacks.onError(msg);
        return;
      }
      // Brief back-off before retry
      await new Promise((r) => setTimeout(r, 500 * attempt));
    }
  }
}
