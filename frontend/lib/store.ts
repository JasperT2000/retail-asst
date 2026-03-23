/**
 * Zustand global state store for the Retail AI Store Assistant.
 *
 * Manages chat history, streaming state, metadata, voice preference,
 * and the active session ID. Voice preference is persisted to localStorage.
 * Chat history is preserved across navigation but cleared on store change.
 */

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { ChatMessage, ChatMetadata } from "./types";

function newSessionId(): string {
  if (
    typeof crypto !== "undefined" &&
    typeof crypto.randomUUID === "function"
  ) {
    return crypto.randomUUID();
  }
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}

interface AppState {
  // Active store context
  currentStore: string | null;

  // Chat
  chatHistory: ChatMessage[];
  isStreaming: boolean;
  streamMetadata: ChatMetadata | null;
  humanNotified: boolean;
  sessionId: string;

  // User preferences (persisted)
  voiceEnabled: boolean;

  // Actions
  setCurrentStore: (slug: string | null) => void;
  addMessage: (message: ChatMessage) => void;
  appendToLastMessage: (token: string) => void;
  updateLastMessage: (content: string) => void;
  setStreaming: (v: boolean) => void;
  setMetadata: (meta: ChatMetadata | null) => void;
  setHumanNotified: (v: boolean) => void;
  toggleVoice: () => void;
  clearHistory: () => void;
  resetSession: () => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      currentStore: null,
      chatHistory: [],
      isStreaming: false,
      streamMetadata: null,
      humanNotified: false,
      sessionId: newSessionId(),
      voiceEnabled: false,

      setCurrentStore: (slug) =>
        set((state) => {
          if (slug === state.currentStore) return state;
          // Switching stores: clear chat history and start a new session
          return {
            currentStore: slug,
            chatHistory: [],
            streamMetadata: null,
            humanNotified: false,
            isStreaming: false,
            sessionId: newSessionId(),
          };
        }),

      addMessage: (message) =>
        set((state) => ({ chatHistory: [...state.chatHistory, message] })),

      appendToLastMessage: (token) =>
        set((state) => {
          if (state.chatHistory.length === 0) return state;
          const updated = [...state.chatHistory];
          const last = updated[updated.length - 1];
          updated[updated.length - 1] = {
            ...last,
            content: last.content + token,
          };
          return { chatHistory: updated };
        }),

      updateLastMessage: (content) =>
        set((state) => {
          if (state.chatHistory.length === 0) return state;
          const updated = [...state.chatHistory];
          updated[updated.length - 1] = {
            ...updated[updated.length - 1],
            content,
          };
          return { chatHistory: updated };
        }),

      setStreaming: (v) => set({ isStreaming: v }),
      setMetadata: (meta) => set({ streamMetadata: meta }),
      setHumanNotified: (v) => set({ humanNotified: v }),

      toggleVoice: () =>
        set((state) => ({ voiceEnabled: !state.voiceEnabled })),

      clearHistory: () =>
        set({
          chatHistory: [],
          streamMetadata: null,
          humanNotified: false,
          sessionId: newSessionId(),
        }),

      resetSession: () => set({ sessionId: newSessionId() }),
    }),
    {
      name: "retail-ai-app",
      // Only persist preferences and session — not ephemeral streaming state
      partialize: (state) => ({
        voiceEnabled: state.voiceEnabled,
        currentStore: state.currentStore,
        chatHistory: state.chatHistory,
        sessionId: state.sessionId,
      }),
    }
  )
);
