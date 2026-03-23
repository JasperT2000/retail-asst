"use client";

/**
 * Voice output component using Google Cloud TTS Neural2 (en-AU-Neural2-C).
 *
 * - Toggle button enables/disables TTS (preference persisted via Zustand).
 * - Automatically speaks when `speakTrigger` increments (after streaming ends).
 * - Fetches audio from the backend POST /tts/synthesize endpoint and plays
 *   it via an HTMLAudioElement — no browser SpeechSynthesis involved.
 */

import { useEffect, useRef } from "react";
import { Volume2, VolumeX } from "lucide-react";
import { useAppStore } from "../lib/store";

interface VoiceOutputProps {
  /** The text to read aloud */
  speakText: string;
  /** Increment to trigger a new read-aloud */
  speakTrigger: number;
}

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

export default function VoiceOutput({ speakText, speakTrigger }: VoiceOutputProps) {
  const { voiceEnabled, toggleVoice } = useAppStore();
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Speak whenever the trigger changes and voice is enabled
  useEffect(() => {
    if (!voiceEnabled || !speakText) return;

    let objectUrl: string | null = null;

    const speak = async () => {
      // Stop any currently playing audio
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.src = "";
      }

      try {
        const res = await fetch(`${BACKEND_URL}/tts/synthesize`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: speakText }),
        });

        if (!res.ok) return;

        const blob = await res.blob();
        objectUrl = URL.createObjectURL(blob);

        const audio = new Audio(objectUrl);
        audioRef.current = audio;
        audio.play();

        // Clean up the object URL once playback ends
        audio.addEventListener("ended", () => {
          if (objectUrl) URL.revokeObjectURL(objectUrl);
        });
      } catch {
        // Silently fail — TTS is enhancement, not critical path
      }
    };

    speak();

    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.src = "";
      }
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  // speakTrigger is the intentional trigger
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [speakTrigger]);

  // Stop audio when voice is disabled mid-playback
  useEffect(() => {
    if (!voiceEnabled && audioRef.current) {
      audioRef.current.pause();
      audioRef.current.src = "";
    }
  }, [voiceEnabled]);

  return (
    <button
      type="button"
      onClick={toggleVoice}
      className={`rounded-full p-2.5 transition-all ${
        voiceEnabled
          ? "bg-blue-100 text-blue-600 ring-1 ring-blue-200"
          : "bg-gray-100 text-gray-400 hover:bg-gray-200"
      }`}
      aria-label={voiceEnabled ? "Disable voice output" : "Enable voice output"}
      title={voiceEnabled ? "Voice output on — tap to mute" : "Enable voice output"}
    >
      {voiceEnabled ? (
        <Volume2 className="h-5 w-5" aria-hidden="true" />
      ) : (
        <VolumeX className="h-5 w-5" aria-hidden="true" />
      )}
    </button>
  );
}
