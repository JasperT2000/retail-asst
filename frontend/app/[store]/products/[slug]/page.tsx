"use client";

/**
 * Full product detail page.
 *
 * Route: /[store]/products/[slug]
 *
 * - Hero: large image + name, brand, pricing (with sale strike-through),
 *   stock badge, aisle location card
 * - Specifications table (collapsible on mobile)
 * - FAQ accordion
 * - Compatible accessories horizontal scroll row
 * - Alternatives grid
 * - "Ask AI about this product" button pre-fills the chat
 */

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { MapPin, ChevronDown, ChevronUp, ArrowLeft, Bot } from "lucide-react";
import { fetchProduct } from "../../../../lib/api";
import { getStoreTheme } from "../../../../lib/types";
import type { ProductDetail } from "../../../../lib/types";

function SpecsSkeleton() {
  return (
    <div className="animate-pulse space-y-2">
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className="h-8 bg-gray-100 rounded" />
      ))}
    </div>
  );
}

function StockBadge({ status }: { status: ProductDetail["stock_status"] }) {
  const map = {
    in_stock: {
      label: "In Stock",
      cls: "bg-green-100 text-green-700 border-green-200",
    },
    low_stock: {
      label: "Low Stock",
      cls: "bg-amber-100 text-amber-700 border-amber-200",
    },
    out_of_stock: {
      label: "Out of Stock",
      cls: "bg-red-100 text-red-700 border-red-200",
    },
  };
  const { label, cls } = map[status];
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-semibold border ${cls}`}
    >
      <span
        className={`w-2 h-2 rounded-full ${
          status === "in_stock"
            ? "bg-green-500"
            : status === "low_stock"
            ? "bg-amber-500"
            : "bg-red-500"
        }`}
      />
      {label}
    </span>
  );
}

export default function ProductPage() {
  const params = useParams();
  const router = useRouter();
  const storeSlug = (params.store as string) ?? "";
  const productSlug = (params.slug as string) ?? "";
  const theme = getStoreTheme(storeSlug);

  const [product, setProduct] = useState<ProductDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [openFaq, setOpenFaq] = useState<number | null>(null);
  const [showAllSpecs, setShowAllSpecs] = useState(false);

  useEffect(() => {
    fetchProduct(storeSlug, productSlug)
      .then(setProduct)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [storeSlug, productSlug]);

  if (loading) {
    return (
      <main className="max-w-5xl mx-auto px-4 sm:px-6 py-10">
        <div className="animate-pulse grid md:grid-cols-2 gap-10">
          <div className="h-80 bg-gray-100 rounded-2xl" />
          <div className="space-y-4">
            <div className="h-6 bg-gray-200 rounded w-3/4" />
            <div className="h-4 bg-gray-100 rounded w-1/2" />
            <div className="h-10 bg-gray-200 rounded w-1/3 mt-4" />
            <SpecsSkeleton />
          </div>
        </div>
      </main>
    );
  }

  if (error || !product) {
    return (
      <main className="max-w-5xl mx-auto px-4 py-10 text-center">
        <p className="text-gray-500 mb-4">Product not found.</p>
        <Link
          href={`/${storeSlug}/products`}
          className="text-sm font-medium hover:underline"
          style={{ color: theme.primary }}
        >
          ← Back to products
        </Link>
      </main>
    );
  }

  const specs =
    typeof product.specifications === "string"
      ? (JSON.parse(product.specifications) as Record<string, string>)
      : product.specifications ?? {};

  const specEntries = Object.entries(specs);
  const visibleSpecs = showAllSpecs ? specEntries : specEntries.slice(0, 6);

  return (
    <main className="max-w-5xl mx-auto px-4 sm:px-6 py-8 space-y-10">
      {/* Back link */}
      <button
        onClick={() => router.back()}
        className="flex items-center gap-1.5 text-sm font-medium hover:opacity-70 transition-opacity"
        style={{ color: theme.primary }}
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        Back
      </button>

      {/* ── Hero ── */}
      <section className="grid md:grid-cols-2 gap-10 items-start">
        {/* Image */}
        <div className="rounded-2xl bg-white border border-gray-100 p-6 flex items-center justify-center h-80 shadow-sm">
          {product.image_url ? (
            <img
              src={product.image_url}
              alt={product.name}
              className="max-h-full max-w-full object-contain"
            />
          ) : (
            <div className="w-20 h-20 rounded-xl bg-gray-100 flex items-center justify-center text-gray-300 text-xs">
              No image
            </div>
          )}
        </div>

        {/* Info */}
        <div className="space-y-4">
          <div>
            <p className="text-sm font-medium text-gray-400 mb-1">
              {product.brand}
            </p>
            <h1 className="text-2xl font-bold text-gray-900 leading-snug">
              {product.name}
            </h1>
          </div>

          {/* Price */}
          <div className="flex items-baseline gap-3">
            <span
              className="text-3xl font-black"
              style={{ color: theme.primary }}
            >
              ${product.price.toFixed(2)}
            </span>
            {product.original_price && (
              <span className="text-lg text-gray-400 line-through">
                ${product.original_price.toFixed(2)}
              </span>
            )}
            {product.original_price && product.original_price > product.price && (
              <span className="text-sm font-semibold text-green-600">
                Save $
                {(product.original_price - product.price).toFixed(2)}
              </span>
            )}
          </div>

          <StockBadge status={product.stock_status} />

          {/* Aisle location */}
          {product.location && (
            <div className="flex items-start gap-2.5 p-3.5 bg-blue-50 border border-blue-100 rounded-xl">
              <MapPin
                className="h-5 w-5 text-blue-500 shrink-0 mt-0.5"
                aria-hidden="true"
              />
              <div>
                <p className="text-sm font-semibold text-blue-800">
                  Find it in store
                </p>
                <p className="text-sm text-blue-600 mt-0.5">
                  {product.location.display_label}
                </p>
                {product.location.section && (
                  <p className="text-xs text-blue-400 mt-0.5">
                    {product.location.section} · {product.location.floor}
                  </p>
                )}
              </div>
            </div>
          )}

          <p className="text-sm text-gray-600 leading-relaxed">
            {product.short_description}
          </p>

          {/* Ask AI button */}
          <Link
            href={`/${storeSlug}?ask=${encodeURIComponent(
              `Tell me about ${product.name}`
            )}`}
            onClick={(e) => {
              e.preventDefault();
              // Navigate to chat with prefill via query param
              router.push(`/${storeSlug}`);
              // Store prefill in sessionStorage for the chat page to pick up
              if (typeof window !== "undefined") {
                sessionStorage.setItem(
                  "prefillMessage",
                  `Tell me about ${product.name}`
                );
              }
            }}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold text-white transition-all hover:opacity-90 active:scale-95"
            style={{ backgroundColor: theme.primary }}
            aria-label={`Ask AI about ${product.name}`}
          >
            <Bot className="h-4 w-4" aria-hidden="true" />
            Ask AI about this product
          </Link>
        </div>
      </section>

      {/* ── Specifications ── */}
      {specEntries.length > 0 && (
        <section>
          <h2 className="text-lg font-bold text-gray-900 mb-4">
            Specifications
          </h2>
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
            <table className="w-full text-sm">
              <tbody>
                {visibleSpecs.map(([key, value], i) => (
                  <tr
                    key={key}
                    className={i % 2 === 0 ? "bg-white" : "bg-gray-50"}
                  >
                    <td className="py-3 px-4 font-medium text-gray-500 w-44">
                      {key}
                    </td>
                    <td className="py-3 px-4 text-gray-800">{String(value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {specEntries.length > 6 && (
            <button
              onClick={() => setShowAllSpecs((v) => !v)}
              className="mt-3 flex items-center gap-1 text-sm font-medium hover:opacity-70 transition-opacity"
              style={{ color: theme.primary }}
            >
              {showAllSpecs ? (
                <>
                  <ChevronUp className="h-4 w-4" />
                  Show fewer specs
                </>
              ) : (
                <>
                  <ChevronDown className="h-4 w-4" />
                  Show all {specEntries.length} specs
                </>
              )}
            </button>
          )}
        </section>
      )}

      {/* ── FAQs ── */}
      {product.faqs.length > 0 && (
        <section>
          <h2 className="text-lg font-bold text-gray-900 mb-4">
            Frequently Asked Questions
          </h2>
          <div className="space-y-2">
            {product.faqs.map((faq, i) => (
              <div
                key={faq.faq_id ?? i}
                className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden"
              >
                <button
                  className="w-full text-left px-5 py-4 flex items-center justify-between gap-4 font-medium text-sm text-gray-800 hover:bg-gray-50 transition-colors"
                  onClick={() => setOpenFaq(openFaq === i ? null : i)}
                  aria-expanded={openFaq === i}
                >
                  <span>{faq.question}</span>
                  {openFaq === i ? (
                    <ChevronUp className="h-4 w-4 text-gray-400 shrink-0" />
                  ) : (
                    <ChevronDown className="h-4 w-4 text-gray-400 shrink-0" />
                  )}
                </button>
                {openFaq === i && (
                  <div className="px-5 pb-4 text-sm text-gray-600 leading-relaxed border-t border-gray-50">
                    {faq.answer}
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ── Compatible Accessories ── */}
      {product.compatible_with.length > 0 && (
        <section>
          <h2 className="text-lg font-bold text-gray-900 mb-4">
            Compatible Accessories
          </h2>
          <div className="flex gap-4 overflow-x-auto pb-2 scrollbar-thin">
            {product.compatible_with.map((acc) => (
              <Link
                key={acc.slug}
                href={`/${storeSlug}/products/${acc.slug}`}
                className="shrink-0 w-44 bg-white rounded-xl border border-gray-100 p-4 shadow-sm hover:shadow-md transition-all hover:-translate-y-0.5"
              >
                <p className="text-xs font-semibold text-gray-800 line-clamp-2 leading-snug">
                  {acc.name}
                </p>
                <p
                  className="text-sm font-bold mt-2"
                  style={{ color: theme.primary }}
                >
                  ${acc.price.toFixed(2)}
                </p>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* ── Alternatives ── */}
      {product.alternatives.length > 0 && (
        <section>
          <h2 className="text-lg font-bold text-gray-900 mb-4">
            You Might Also Consider
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
            {product.alternatives.map((alt) => (
              <Link
                key={alt.slug}
                href={`/${storeSlug}/products/${alt.slug}`}
                className="bg-white rounded-xl border border-gray-100 p-4 shadow-sm hover:shadow-md transition-all hover:-translate-y-0.5"
              >
                <p className="text-xs font-semibold text-gray-800 line-clamp-2 leading-snug">
                  {alt.name}
                </p>
                <p
                  className="text-sm font-bold mt-2"
                  style={{ color: theme.primary }}
                >
                  ${alt.price.toFixed(2)}
                </p>
              </Link>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}
