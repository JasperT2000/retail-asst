"use client";

/**
 * Monitoring dashboard page.
 *
 * Route: /monitoring
 *
 * PIN-protected. On load, prompts for the MONITOR_PIN env value (sent as
 * X-Monitor-PIN header). Shows query volume, intent distribution, confidence
 * buckets, latency percentiles, and escalation/error rates.
 */

import { useState, useEffect, useCallback } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { Activity, RefreshCw, Lock } from "lucide-react";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

interface LatencyStats {
  avg: number;
  p50: number;
  p95: number;
  p99: number;
  samples: number;
}

interface MetricsSummary {
  uptime_seconds: number;
  total_queries: number;
  total_escalations: number;
  escalation_rate: number;
  total_errors: number;
  error_rate: number;
  intent_distribution: Record<string, number>;
  store_distribution: Record<string, number>;
  llm_provider_distribution: Record<string, number>;
  confidence_distribution: Record<string, number>;
  latency_ms: LatencyStats;
}

function formatUptime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

function StatCard({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: string | number;
  sub?: string;
  accent?: string;
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
      <p className="text-xs font-semibold uppercase tracking-widest text-gray-400 mb-1">
        {label}
      </p>
      <p
        className="text-3xl font-black text-gray-900"
        style={accent ? { color: accent } : undefined}
      >
        {value}
      </p>
      {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
    </div>
  );
}

const BAR_COLORS = [
  "#6366f1",
  "#8b5cf6",
  "#ec4899",
  "#f59e0b",
  "#10b981",
  "#3b82f6",
  "#ef4444",
  "#14b8a6",
];

function DistributionChart({
  title,
  data,
}: {
  title: string;
  data: Record<string, number>;
}) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
  const chartData = entries.map(([name, value]) => ({ name, value }));

  if (chartData.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
        <h3 className="text-sm font-bold text-gray-700 mb-3">{title}</h3>
        <p className="text-sm text-gray-400">No data yet.</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
      <h3 className="text-sm font-bold text-gray-700 mb-4">{title}</h3>
      <ResponsiveContainer width="100%" height={160}>
        <BarChart data={chartData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
          <XAxis
            dataKey="name"
            tick={{ fontSize: 11 }}
            interval={0}
            angle={chartData.length > 4 ? -20 : 0}
            textAnchor={chartData.length > 4 ? "end" : "middle"}
            height={chartData.length > 4 ? 40 : 20}
          />
          <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
          <Tooltip
            contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e5e7eb" }}
          />
          <Bar dataKey="value" radius={[4, 4, 0, 0]}>
            {chartData.map((_, i) => (
              <Cell key={i} fill={BAR_COLORS[i % BAR_COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

const CONFIDENCE_LABELS: Record<string, string> = {
  low: "Low (<0.4)",
  medium_low: "Med-Low (0.4–0.65)",
  medium_high: "Med-High (0.65–0.8)",
  high: "High (≥0.8)",
};

export default function MonitoringPage() {
  const [pin, setPin] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [data, setData] = useState<MetricsSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  const fetchMetrics = useCallback(
    async (pinValue: string) => {
      setLoading(true);
      setError(null);
      try {
        const headers: Record<string, string> = {};
        if (pinValue) headers["X-Monitor-PIN"] = pinValue;
        const res = await fetch(`${BACKEND_URL}/monitoring/summary`, { headers });
        if (res.status === 401) {
          setError("Invalid PIN. Please try again.");
          setSubmitted(false);
          return;
        }
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        setData(json);
        setLastRefresh(new Date());
      } catch (e) {
        setError("Failed to load metrics. Is the backend running?");
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const handlePinSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitted(true);
    fetchMetrics(pin);
  };

  if (!submitted) {
    return (
      <main className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-8 w-full max-w-sm">
          <div className="flex items-center gap-3 mb-6">
            <Lock className="h-5 w-5 text-indigo-500" />
            <h1 className="text-lg font-bold text-gray-900">Monitoring Dashboard</h1>
          </div>
          <form onSubmit={handlePinSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Monitor PIN{" "}
                <span className="text-gray-400 font-normal">(leave blank if not set)</span>
              </label>
              <input
                type="password"
                value={pin}
                onChange={(e) => setPin(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
                placeholder="Enter PIN"
              />
            </div>
            <button
              type="submit"
              className="w-full py-2.5 rounded-lg bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700 transition-colors"
            >
              View Dashboard
            </button>
          </form>
        </div>
      </main>
    );
  }

  return (
    <main className="max-w-6xl mx-auto px-4 sm:px-6 py-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Activity className="h-6 w-6 text-indigo-500" />
          <h1 className="text-2xl font-bold text-gray-900">Monitoring Dashboard</h1>
        </div>
        <button
          onClick={() => fetchMetrics(pin)}
          disabled={loading}
          className="flex items-center gap-1.5 text-sm font-medium text-indigo-600 hover:opacity-70 transition-opacity disabled:opacity-40"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {lastRefresh && (
        <p className="text-xs text-gray-400">
          Last updated: {lastRefresh.toLocaleTimeString()}
        </p>
      )}

      {error && (
        <div className="p-4 bg-red-50 border border-red-100 rounded-xl text-sm text-red-600">
          {error}
        </div>
      )}

      {loading && !data && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="animate-pulse bg-white rounded-xl border border-gray-100 h-24"
            />
          ))}
        </div>
      )}

      {data && (
        <>
          {/* Top-line stats */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <StatCard
              label="Total Queries"
              value={data.total_queries.toLocaleString()}
              sub={`Uptime: ${formatUptime(data.uptime_seconds)}`}
            />
            <StatCard
              label="Escalation Rate"
              value={`${(data.escalation_rate * 100).toFixed(1)}%`}
              sub={`${data.total_escalations} escalations`}
              accent={data.escalation_rate > 0.15 ? "#ef4444" : undefined}
            />
            <StatCard
              label="Error Rate"
              value={`${(data.error_rate * 100).toFixed(1)}%`}
              sub={`${data.total_errors} errors`}
              accent={data.error_rate > 0.05 ? "#ef4444" : undefined}
            />
            <StatCard
              label="Avg Latency"
              value={`${data.latency_ms.avg.toFixed(0)}ms`}
              sub={`p95: ${data.latency_ms.p95.toFixed(0)}ms · p99: ${data.latency_ms.p99.toFixed(0)}ms`}
            />
          </div>

          {/* Charts row 1 */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <DistributionChart
              title="Queries by Intent"
              data={data.intent_distribution}
            />
            <DistributionChart
              title="Queries by Store"
              data={data.store_distribution}
            />
            <DistributionChart
              title="LLM Provider"
              data={data.llm_provider_distribution}
            />
          </div>

          {/* Confidence distribution */}
          <DistributionChart
            title="Confidence Score Distribution"
            data={Object.fromEntries(
              Object.entries(data.confidence_distribution).map(([k, v]) => [
                CONFIDENCE_LABELS[k] ?? k,
                v,
              ])
            )}
          />

          {/* Latency table */}
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
            <h3 className="text-sm font-bold text-gray-700 mb-4">
              Latency Percentiles
              <span className="ml-2 text-xs text-gray-400 font-normal">
                (last {data.latency_ms.samples} queries)
              </span>
            </h3>
            <div className="grid grid-cols-4 gap-4">
              {[
                { label: "Average", value: data.latency_ms.avg },
                { label: "p50 (Median)", value: data.latency_ms.p50 },
                { label: "p95", value: data.latency_ms.p95 },
                { label: "p99", value: data.latency_ms.p99 },
              ].map(({ label, value }) => (
                <div key={label} className="text-center">
                  <p className="text-2xl font-black text-indigo-600">
                    {value.toFixed(0)}
                    <span className="text-sm font-normal text-gray-400 ml-0.5">ms</span>
                  </p>
                  <p className="text-xs text-gray-500 mt-1">{label}</p>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </main>
  );
}
