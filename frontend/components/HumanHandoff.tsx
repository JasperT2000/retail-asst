"use client";

/**
 * Human handoff indicator banner.
 *
 * Shown above the chat input when the pipeline has notified a Slack agent
 * (low confidence, payment intent, live demo, or explicit escalation request).
 */

import { Bell } from "lucide-react";

export default function HumanHandoff() {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-center gap-2.5 px-4 py-2.5 bg-amber-50 border-b border-amber-200 text-amber-800 text-sm"
    >
      <Bell className="h-4 w-4 shrink-0 text-amber-500" aria-hidden="true" />
      <span>
        A team member has been notified and will be with you shortly.
      </span>
    </div>
  );
}
