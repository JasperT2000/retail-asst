"use client";

/**
 * Store policies page.
 *
 * Route: /[store]/policies
 *
 * Displays all policy documents as expandable cards. Each card shows the
 * policy type icon, title, summary, and an accordion for the full text.
 */

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { ChevronDown, ChevronUp, FileText } from "lucide-react";
import { fetchPolicies } from "../../../lib/api";
import { getStoreTheme } from "../../../lib/types";
import type { PolicyDoc } from "../../../lib/types";

const POLICY_ICONS: Record<string, string> = {
  returns: "↩️",
  warranty: "🛡️",
  price_match: "💰",
  loyalty: "⭐",
  layby: "📦",
  delivery: "🚚",
  privacy: "🔒",
  trade_in: "🔄",
};

function PolicyCardSkeleton() {
  return (
    <div className="animate-pulse bg-white rounded-2xl border border-gray-100 p-6 space-y-3 shadow-sm">
      <div className="h-5 bg-gray-200 rounded w-2/5" />
      <div className="h-3 bg-gray-100 rounded w-4/5" />
      <div className="h-3 bg-gray-100 rounded w-3/5" />
    </div>
  );
}

interface PolicyCardProps {
  policy: PolicyDoc;
  primaryColor: string;
}

function PolicyCard({ policy, primaryColor }: PolicyCardProps) {
  const [expanded, setExpanded] = useState(false);
  const icon = POLICY_ICONS[policy.policy_type] ?? "📄";
  const typeLabel = policy.policy_type
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="p-6">
        <div className="flex items-start gap-4">
          <span className="text-2xl shrink-0 mt-0.5" aria-hidden="true">
            {icon}
          </span>
          <div className="flex-1 min-w-0">
            <p
              className="text-xs font-semibold uppercase tracking-widest mb-1"
              style={{ color: primaryColor }}
            >
              {typeLabel}
            </p>
            <h2 className="text-base font-bold text-gray-900 leading-snug">
              {policy.title}
            </h2>
            {policy.summary && (
              <p className="text-sm text-gray-500 mt-2 leading-relaxed">
                {policy.summary}
              </p>
            )}
            {policy.last_updated && (
              <p className="text-xs text-gray-300 mt-2">
                Last updated: {policy.last_updated}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Expand button */}
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-6 py-3 text-sm font-medium border-t border-gray-50 hover:bg-gray-50 transition-colors"
        style={{ color: primaryColor }}
        aria-expanded={expanded}
      >
        <span>{expanded ? "Hide full policy" : "Read full policy"}</span>
        {expanded ? (
          <ChevronUp className="h-4 w-4" aria-hidden="true" />
        ) : (
          <ChevronDown className="h-4 w-4" aria-hidden="true" />
        )}
      </button>

      {/* Full policy text */}
      {expanded && (
        <div className="px-6 pb-6 border-t border-gray-50">
          <div className="pt-4 text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
            {policy.content}
          </div>
        </div>
      )}
    </div>
  );
}

export default function PoliciesPage() {
  const params = useParams();
  const storeSlug = (params.store as string) ?? "";
  const theme = getStoreTheme(storeSlug);

  const [policies, setPolicies] = useState<PolicyDoc[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    fetchPolicies(storeSlug)
      .then(setPolicies)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [storeSlug]);

  return (
    <main className="max-w-3xl mx-auto px-4 sm:px-6 py-8 space-y-6">
      <div className="flex items-center gap-3">
        <FileText
          className="h-6 w-6"
          style={{ color: theme.primary }}
          aria-hidden="true"
        />
        <h1 className="text-2xl font-bold text-gray-900">Store Policies</h1>
      </div>

      {loading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <PolicyCardSkeleton key={i} />
          ))}
        </div>
      ) : error ? (
        <div className="text-center py-16 text-gray-400">
          <p>Unable to load policies. Please try again later.</p>
        </div>
      ) : policies.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <p>No policies available for this store yet.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {policies.map((pol) => (
            <PolicyCard
              key={pol.policy_id}
              policy={pol}
              primaryColor={theme.primary}
            />
          ))}
        </div>
      )}
    </main>
  );
}
