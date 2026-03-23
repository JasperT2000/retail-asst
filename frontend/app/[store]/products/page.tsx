"use client";

/**
 * Products listing page for a store.
 *
 * Route: /[store]/products
 *
 * - Category filter tabs at the top
 * - Responsive grid of ProductCard components (3 cols desktop, 2 tablet, 1 mobile)
 * - Pagination controls
 * - Skeleton loaders while data fetches
 */

import { useState, useEffect } from "react";
import { useParams, useSearchParams } from "next/navigation";
import ProductCard from "../../../components/ProductCard";
import { fetchCategories, fetchProducts } from "../../../lib/api";
import { getStoreTheme } from "../../../lib/types";
import type { Category, ProductListItem } from "../../../lib/types";

const PAGE_SIZE = 12;

function ProductSkeleton() {
  return (
    <div className="animate-pulse rounded-xl bg-white border border-gray-100 overflow-hidden">
      <div className="h-40 bg-gray-100" />
      <div className="p-4 space-y-2">
        <div className="h-3 bg-gray-200 rounded w-4/5" />
        <div className="h-3 bg-gray-200 rounded w-3/5" />
        <div className="h-4 bg-gray-200 rounded w-1/3 mt-4" />
      </div>
    </div>
  );
}

export default function ProductsPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const storeSlug = (params.store as string) ?? "";
  const theme = getStoreTheme(storeSlug);

  const initialCategory = searchParams.get("category") ?? null;
  const [activeCategory, setActiveCategory] = useState<string | null>(
    initialCategory
  );
  const [currentPage, setCurrentPage] = useState(1);

  const [categories, setCategories] = useState<Category[]>([]);
  const [products, setProducts] = useState<ProductListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loadingCats, setLoadingCats] = useState(true);
  const [loadingProds, setLoadingProds] = useState(true);

  // Fetch categories once
  useEffect(() => {
    fetchCategories(storeSlug)
      .then(setCategories)
      .catch(() => setCategories([]))
      .finally(() => setLoadingCats(false));
  }, [storeSlug]);

  // Fetch products when filter / page changes
  useEffect(() => {
    setLoadingProds(true);
    fetchProducts(storeSlug, {
      categorySlug: activeCategory ?? undefined,
      page: currentPage,
      pageSize: PAGE_SIZE,
    })
      .then((data) => {
        setProducts(data.products);
        setTotal(data.total);
      })
      .catch(() => {
        setProducts([]);
        setTotal(0);
      })
      .finally(() => setLoadingProds(false));
  }, [storeSlug, activeCategory, currentPage]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const handleCategoryChange = (slug: string | null) => {
    setActiveCategory(slug);
    setCurrentPage(1);
  };

  return (
    <main className="max-w-7xl mx-auto px-4 sm:px-6 py-8 space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Browse Products</h1>

      {/* Category filter tabs */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-thin">
        <button
          onClick={() => handleCategoryChange(null)}
          className="shrink-0 px-4 py-2 rounded-full text-sm font-medium transition-all"
          style={{
            backgroundColor: !activeCategory ? theme.primary : "#f3f4f6",
            color: !activeCategory
              ? getStoreTheme(storeSlug).text
              : "#374151",
          }}
          aria-pressed={!activeCategory}
        >
          All
        </button>

        {loadingCats
          ? [1, 2, 3].map((i) => (
              <div
                key={i}
                className="shrink-0 animate-pulse w-20 h-9 rounded-full bg-gray-200"
              />
            ))
          : categories.map((cat) => (
              <button
                key={cat.slug}
                onClick={() => handleCategoryChange(cat.slug)}
                className="shrink-0 px-4 py-2 rounded-full text-sm font-medium transition-all"
                style={{
                  backgroundColor:
                    activeCategory === cat.slug ? theme.primary : "#f3f4f6",
                  color:
                    activeCategory === cat.slug
                      ? getStoreTheme(storeSlug).text
                      : "#374151",
                }}
                aria-pressed={activeCategory === cat.slug}
              >
                {cat.name}
              </button>
            ))}
      </div>

      {/* Results count */}
      {!loadingProds && (
        <p className="text-sm text-gray-400">
          {total} product{total !== 1 ? "s" : ""} found
        </p>
      )}

      {/* Product grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
        {loadingProds
          ? Array.from({ length: PAGE_SIZE }).map((_, i) => (
              <ProductSkeleton key={i} />
            ))
          : products.map((p) => (
              <ProductCard
                key={p.slug}
                product={p}
                storeSlug={storeSlug}
                primaryColor={theme.primary}
              />
            ))}
      </div>

      {/* Pagination */}
      {!loadingProds && totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 pt-4">
          <button
            onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
            disabled={currentPage === 1}
            className="px-4 py-2 rounded-lg text-sm font-medium bg-white border border-gray-200 disabled:opacity-40 hover:bg-gray-50 transition-colors"
          >
            ← Previous
          </button>
          <span className="text-sm text-gray-500">
            Page {currentPage} of {totalPages}
          </span>
          <button
            onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
            disabled={currentPage === totalPages}
            className="px-4 py-2 rounded-lg text-sm font-medium bg-white border border-gray-200 disabled:opacity-40 hover:bg-gray-50 transition-colors"
          >
            Next →
          </button>
        </div>
      )}
    </main>
  );
}
