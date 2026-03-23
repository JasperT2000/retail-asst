"use client";

/**
 * Landing page — hero section + store selector grid.
 *
 * Fetches live store data (with category/product counts) from the backend.
 * Shows skeleton cards while loading.
 */

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Bot, Zap, ShoppingBag } from "lucide-react";
import { fetchStores } from "../lib/api";
import type { Store } from "../lib/types";

const STORE_META: Record<
  string,
  { tagline: string; emoji: string; textColor: string }
> = {
  jbhifi: {
    tagline: "TVs, Laptops, Audio, Gaming & More",
    emoji: "🎮",
    textColor: "#1a1a1a",
  },
  bunnings: {
    tagline: "Tools, Hardware, Garden & Home Improvement",
    emoji: "🔨",
    textColor: "#ffffff",
  },
  babybunting: {
    tagline: "Prams, Car Seats, Nursery & More",
    emoji: "👶",
    textColor: "#ffffff",
  },
  supercheapauto: {
    tagline: "Car Care, Tools, Audio & Batteries",
    emoji: "🚗",
    textColor: "#ffffff",
  },
};

function StoreCardSkeleton() {
  return (
    <div className="animate-pulse rounded-2xl bg-gray-200 h-44" />
  );
}

interface StoreCardProps {
  store: Store;
  onClick: () => void;
}

function StoreCard({ store, onClick }: StoreCardProps) {
  const meta = STORE_META[store.slug];
  const textColor = meta?.textColor ?? "#ffffff";

  return (
    <button
      onClick={onClick}
      className="group relative rounded-2xl p-8 text-left transition-all duration-200 hover:scale-[1.02] hover:shadow-2xl shadow-md overflow-hidden focus:outline-none focus-visible:ring-4"
      style={{
        backgroundColor: store.primary_color,
        ["--tw-ring-color" as string]: store.primary_color,
      }}
      aria-label={`Open ${store.name} AI assistant`}
    >
      {/* Decorative background circle */}
      <div
        className="absolute -right-10 -top-10 w-40 h-40 rounded-full opacity-10 pointer-events-none"
        style={{ backgroundColor: textColor }}
      />

      <div className="relative z-10">
        <div className="text-3xl mb-3" aria-hidden="true">
          {meta?.emoji}
        </div>
        <h2
          className="text-xl font-bold mb-1 leading-tight"
          style={{ color: textColor }}
        >
          {store.name}
        </h2>
        <p
          className="text-sm mb-4 leading-snug opacity-80"
          style={{ color: textColor }}
        >
          {meta?.tagline}
        </p>

        {/* Counts */}
        <div
          className="flex gap-4 text-xs font-medium opacity-70"
          style={{ color: textColor }}
        >
          {(store.category_count ?? 0) > 0 && (
            <span>{store.category_count} categories</span>
          )}
          {(store.product_count ?? 0) > 0 && (
            <span>{store.product_count} products</span>
          )}
        </div>
      </div>

      {/* Hover arrow */}
      <span
        className="absolute bottom-6 right-6 text-2xl opacity-0 group-hover:opacity-60 transition-opacity"
        style={{ color: textColor }}
        aria-hidden="true"
      >
        →
      </span>
    </button>
  );
}

export default function HomePage() {
  const router = useRouter();
  const [stores, setStores] = useState<Store[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStores()
      .then(setStores)
      .catch(() => setStores([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="min-h-screen bg-gray-50">
      {/* Hero */}
      <section className="bg-white border-b border-gray-100 py-20 px-6">
        <div className="max-w-3xl mx-auto text-center space-y-6">
          <div className="inline-flex items-center gap-2 bg-gray-100 rounded-full px-4 py-2 text-sm text-gray-600 font-medium">
            <Zap className="h-4 w-4 text-yellow-500" aria-hidden="true" />
            Hybrid Graph + Vector RAG · Neo4j + Groq
          </div>

          <h1 className="text-5xl sm:text-6xl font-black tracking-tight text-gray-900 leading-tight">
            Your AI store assistant.
            <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-violet-600">
              Ask anything.
            </span>
          </h1>

          <p className="text-xl text-gray-500 max-w-2xl mx-auto leading-relaxed">
            Find products, check stock, locate aisles, and understand store
            policies — all in plain language, streaming in real time.
          </p>

          <div className="flex flex-wrap justify-center gap-6 text-sm text-gray-400 pt-2">
            <span className="flex items-center gap-1.5">
              <Bot className="h-4 w-4" aria-hidden="true" />
              Streaming AI responses
            </span>
            <span className="flex items-center gap-1.5">
              <ShoppingBag className="h-4 w-4" aria-hidden="true" />
              4 stores · 400 products
            </span>
            <span className="flex items-center gap-1.5">
              <Zap className="h-4 w-4" aria-hidden="true" />
              Voice-enabled
            </span>
          </div>
        </div>
      </section>

      {/* Store selector */}
      <section className="max-w-3xl mx-auto py-16 px-6">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-8 text-center">
          Select your store to get started
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          {loading
            ? [1, 2, 3, 4].map((i) => <StoreCardSkeleton key={i} />)
            : stores.map((store) => (
                <StoreCard
                  key={store.slug}
                  store={store}
                  onClick={() => router.push(`/${store.slug}`)}
                />
              ))}
        </div>
      </section>

      <footer className="text-center text-xs text-gray-300 pb-10">
        Retail AI Store Assistant · LinkedIn Portfolio Project
      </footer>
    </main>
  );
}
