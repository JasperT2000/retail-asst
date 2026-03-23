"use client";

/**
 * Reusable store selector grid.
 *
 * Pure presentational component — accepts stores as props and calls
 * onSelect when a card is clicked. Used by the landing page.
 */

import type { Store } from "../lib/types";

const STORE_META: Record<string, { tagline: string; emoji: string; textColor: string }> = {
  jbhifi: { tagline: "TVs, Laptops, Audio, Gaming & More", emoji: "🎮", textColor: "#1a1a1a" },
  bunnings: { tagline: "Tools, Hardware, Garden & Home", emoji: "🔨", textColor: "#ffffff" },
  babybunting: { tagline: "Prams, Car Seats, Nursery & More", emoji: "👶", textColor: "#ffffff" },
  supercheapauto: { tagline: "Car Care, Tools, Audio & Batteries", emoji: "🚗", textColor: "#ffffff" },
};

interface StoreSelectorProps {
  stores: Store[];
  onSelect: (slug: string) => void;
}

export default function StoreSelector({ stores, onSelect }: StoreSelectorProps) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 w-full max-w-2xl">
      {stores.map((store) => {
        const meta = STORE_META[store.slug];
        const textColor = meta?.textColor ?? "#ffffff";

        return (
          <button
            key={store.slug}
            onClick={() => onSelect(store.slug)}
            className="group relative rounded-2xl p-8 text-left transition-all duration-200 hover:scale-[1.02] hover:shadow-2xl shadow-md overflow-hidden focus:outline-none"
            style={{ backgroundColor: store.primary_color }}
            aria-label={`Select ${store.name}`}
          >
            <div
              className="absolute -right-10 -top-10 w-40 h-40 rounded-full opacity-10 pointer-events-none"
              style={{ backgroundColor: textColor }}
            />
            <div className="relative z-10">
              <div className="text-3xl mb-3">{meta?.emoji}</div>
              <h2 className="text-xl font-bold mb-1" style={{ color: textColor }}>
                {store.name}
              </h2>
              <p className="text-sm opacity-80" style={{ color: textColor }}>
                {meta?.tagline}
              </p>
            </div>
          </button>
        );
      })}
    </div>
  );
}
