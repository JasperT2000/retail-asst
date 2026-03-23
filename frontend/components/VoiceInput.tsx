"use client";

/**
 * Voice input component using the Web Speech API (browser-native, no API cost).
 *
 * Renders a microphone button that toggles speech recognition. On a successful
 * recognition result, fires onTranscript with the text. If autoSubmit is true
 * the caller's onSubmit is invoked immediately after (for hands-free queries).
 *
 * Gracefully hidden on browsers that do not support SpeechRecognition.
 */

import { useState, useRef, useCallback, useEffect } from "react";
import { Mic, MicOff } from "lucide-react";

interface VoiceInputProps {
  onTranscript: (text: string) => void;
  onSubmit?: (text: string) => void;
  disabled?: boolean;
  autoSubmit?: boolean;
}

export default function VoiceInput({
  onTranscript,
  onSubmit,
  disabled = false,
  autoSubmit = true,
}: VoiceInputProps) {
  const [isListening, setIsListening] = useState(false);
  const [supported, setSupported] = useState(false);
  const recognitionRef = useRef<SpeechRecognition | null>(null);

  useEffect(() => {
    // Check support client-side only
    const has =
      typeof window !== "undefined" &&
      ("SpeechRecognition" in window || "webkitSpeechRecognition" in window);
    setSupported(has);
  }, []);

  const toggle = useCallback(() => {
    if (!supported) return;

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const SR = (window as any).SpeechRecognition ?? (window as any).webkitSpeechRecognition;

    if (isListening) {
      recognitionRef.current?.stop();
      setIsListening(false);
      return;
    }

    const recognition: SpeechRecognition = new SR();
    recognition.lang = "en-AU";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      const transcript = event.results[0][0].transcript;
      onTranscript(transcript);
      if (autoSubmit && onSubmit) {
        onSubmit(transcript);
      }
    };

    recognition.onend = () => setIsListening(false);
    recognition.onerror = () => setIsListening(false);

    recognitionRef.current = recognition;
    recognition.start();
    setIsListening(true);
  }, [isListening, supported, onTranscript, onSubmit, autoSubmit]);

  if (!supported) return null;

  return (
    <button
      type="button"
      onClick={toggle}
      disabled={disabled}
      className={`relative rounded-full p-2.5 transition-all ${
        isListening
          ? "bg-red-100 text-red-600 ring-2 ring-red-300"
          : "bg-gray-100 text-gray-500 hover:bg-gray-200"
      } disabled:opacity-40 disabled:cursor-not-allowed`}
      aria-label={isListening ? "Stop voice input" : "Start voice input"}
      title={isListening ? "Listening… tap to stop" : "Voice input (en-AU)"}
    >
      {isListening ? (
        <>
          {/* Pulse ring animation */}
          <span className="absolute inset-0 rounded-full bg-red-400 opacity-20 animate-ping" />
          <MicOff className="h-5 w-5 relative" aria-hidden="true" />
        </>
      ) : (
        <Mic className="h-5 w-5" aria-hidden="true" />
      )}
    </button>
  );
}
