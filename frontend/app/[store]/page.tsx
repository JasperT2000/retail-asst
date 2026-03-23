"use client";

/**
 * Main chat page for a store — two-column layout on desktop.
 *
 * Left (60%): Chat interface powered by RAGPipeline SSE stream.
 * Right (40%): Knowledge panel with Products / Categories / Policies tabs.
 *
 * Clicking a product in the knowledge panel pre-fills the chat input.
 * On mobile the knowledge panel is hidden (accessible via the Products nav link).
 *
 * Route: /[store]
 */

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { MapPin } from "lucide-react";
import ChatInterface from "../../components/ChatInterface";
import { fetchCategories, fetchProducts, fetchPolicies } from "../../lib/api";
import { getStoreTheme } from "../../lib/types";
import type { Category, ProductListItem, PolicyDoc } from "../../lib/types";

type PanelTab = "products" | "categories" | "policies";

function PanelSkeleton() {
  return (
    <div className="space-y-2 p-4">
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className="animate-pulse rounded-lg bg-gray-100 h-16" />
      ))}
    </div>
  );
}

function StockBadge({ status }: { status: ProductListItem["stock_status"] }) {
  const map = {
    in_stock: { label: "In Stock", cls: "bg-green-100 text-green-700" },
    low_stock: { label: "Low", cls: "bg-amber-100 text-amber-700" },
    out_of_stock: { label: "Out", cls: "bg-red-100 text-red-700" },
  };
  const { label, cls } = map[status];
  return (
    <span className={`text-[9px] font-semibold px-1.5 py-0.5 rounded-full ${cls}`}>
      {label}
    </span>
  );
}

export default function StorePage() {
  const params = useParams();
  const storeSlug = (params.store as string) ?? "";
  const theme = getStoreTheme(storeSlug);

  const [activeTab, setActiveTab] = useState<PanelTab>("products");
  const [prefillMessage, setPrefillMessage] = useState("");

  const [categories, setCategories] = useState<Category[]>([]);
  const [products, setProducts] = useState<ProductListItem[]>([]);
  const [policies, setPolicies] = useState<PolicyDoc[]>([]);
  const [panelLoading, setPanelLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetchCategories(storeSlug).catch(() => [] as Category[]),
      fetchProducts(storeSlug, { pageSize: 10 }).catch(() => ({
        products: [] as ProductListItem[],
        total: 0,
        page: 1,
        page_size: 10,
      })),
      fetchPolicies(storeSlug).catch(() => [] as PolicyDoc[]),
    ]).then(([cats, prodPage, pols]) => {
      setCategories(cats);
      setProducts(prodPage.products);
      setPolicies(pols);
    }).finally(() => setPanelLoading(false));
  }, [storeSlug]);

  const TABS: PanelTab[] = ["products", "categories", "policies"];

  return (
    /* Full-height layout minus the 56px nav */
    <div className="flex h-[calc(100vh-3.5rem)]">
      {/* ─── Left: Chat (full width on mobile, 60% on desktop) ─── */}
      <div className="flex-1 lg:max-w-[60%] min-w-0 flex flex-col">
        <ChatInterface
          storeSlug={storeSlug}
          primaryColor={theme.primary}
          prefillMessage={prefillMessage}
          onPrefillConsumed={() => setPrefillMessage("")}
        />
      </div>

      {/* ─── Right: Knowledge panel (desktop only, 40%) ─── */}
      <aside className="hidden lg:flex lg:w-[40%] flex-col bg-white border-l border-gray-200 overflow-hidden">
        {/* Tab bar */}
        <div
          className="flex border-b border-gray-100 px-4 pt-3 shrink-0"
          role="tablist"
          aria-label="Knowledge panel"
        >
          {TABS.map((tab) => (
            <button
              key={tab}
              role="tab"
              aria-selected={activeTab === tab}
              onClick={() => setActiveTab(tab)}
              className="capitalize px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors"
              style={{
                borderColor: activeTab === tab ? theme.primary : "transparent",
                color: activeTab === tab ? "#111827" : "#9ca3af",
              }}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div
          role="tabpanel"
          className="flex-1 overflow-y-auto scrollbar-thin"
        >
          {panelLoading ? (
            <PanelSkeleton />
          ) : activeTab === "products" ? (
            <div className="p-3 space-y-2">
              {products.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-10">
                  No products loaded yet.
                </p>
              ) : (
                products.map((p) => (
                  <button
                    key={p.slug}
                    onClick={() =>
                      setPrefillMessage(`Tell me about ${p.name}`)
                    }
                    className="w-full text-left flex items-center gap-3 p-3 rounded-lg hover:bg-gray-50 border border-gray-100 transition-colors"
                    aria-label={`Ask about ${p.name}`}
                  >
                    {/* Thumbnail */}
                    <div className="w-12 h-12 bg-gray-100 rounded-lg shrink-0 overflow-hidden flex items-center justify-center">
                      {p.image_url ? (
                        <img
                          src={p.image_url}
                          alt=""
                          className="w-full h-full object-contain"
                        />
                      ) : (
                        <span className="text-gray-300 text-xs">?</span>
                      )}
                    </div>

                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-semibold text-gray-800 line-clamp-2 leading-snug">
                        {p.name}
                      </p>
                      <div className="flex items-center gap-1.5 mt-1">
                        <span className="text-xs font-bold text-gray-900">
                          ${p.price.toFixed(2)}
                        </span>
                        <StockBadge status={p.stock_status} />
                      </div>
                      {p.aisle_label && (
                        <div className="flex items-center gap-0.5 mt-0.5 text-[10px] text-gray-400">
                          <MapPin className="h-2.5 w-2.5 shrink-0" />
                          <span className="truncate">{p.aisle_label}</span>
                        </div>
                      )}
                    </div>
                  </button>
                ))
              )}

              <Link
                href={`/${storeSlug}/products`}
                className="block text-center text-xs py-3 font-medium hover:underline"
                style={{ color: theme.primary }}
              >
                Browse all products →
              </Link>
            </div>
          ) : activeTab === "categories" ? (
            <div className="p-3 space-y-2">
              {categories.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-10">
                  No categories loaded yet.
                </p>
              ) : (
                categories.map((c) => (
                  <Link
                    key={c.slug}
                    href={`/${storeSlug}/products?category=${c.slug}`}
                    className="flex items-center justify-between p-3 rounded-lg hover:bg-gray-50 border border-gray-100 transition-colors"
                  >
                    <span className="text-sm font-medium text-gray-800">
                      {c.name}
                    </span>
                    {c.product_count !== undefined && (
                      <span className="text-xs text-gray-400">
                        {c.product_count}
                      </span>
                    )}
                  </Link>
                ))
              )}
            </div>
          ) : (
            /* Policies */
            <div className="p-3 space-y-2">
              {policies.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-10">
                  No policies available yet.
                </p>
              ) : (
                policies.map((pol) => (
                  <Link
                    key={pol.policy_id}
                    href={`/${storeSlug}/policies`}
                    className="block p-3 rounded-lg hover:bg-gray-50 border border-gray-100 transition-colors"
                  >
                    <p className="text-xs font-semibold text-gray-800 capitalize">
                      {pol.policy_type.replace(/_/g, " ")}
                    </p>
                    <p className="text-xs font-medium text-gray-700 mt-0.5">
                      {pol.title}
                    </p>
                    {pol.summary && (
                      <p className="text-xs text-gray-400 mt-1 line-clamp-2 leading-relaxed">
                        {pol.summary}
                      </p>
                    )}
                  </Link>
                ))
              )}

              <Link
                href={`/${storeSlug}/policies`}
                className="block text-center text-xs py-3 font-medium hover:underline"
                style={{ color: theme.primary }}
              >
                View all policies →
              </Link>
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}
