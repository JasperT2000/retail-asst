"use client";

/**
 * Category grid — displays store categories as clickable cards with product counts.
 *
 * Skeleton loaders are shown while data fetches. Clicking navigates to the
 * products page filtered to that category.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { fetchCategories } from "../lib/api";
import type { Category } from "../lib/types";

interface CategoryGridProps {
  storeSlug: string;
  primaryColor?: string;
}

function CategorySkeleton() {
  return (
    <div className="animate-pulse rounded-xl bg-gray-100 h-24" />
  );
}

export default function CategoryGrid({
  storeSlug,
  primaryColor = "#6366f1",
}: CategoryGridProps) {
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchCategories(storeSlug)
      .then(setCategories)
      .catch(() => setCategories([]))
      .finally(() => setLoading(false));
  }, [storeSlug]);

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
      {loading
        ? [1, 2, 3, 4, 5, 6].map((i) => <CategorySkeleton key={i} />)
        : categories.map((cat) => (
            <Link
              key={cat.slug}
              href={`/${storeSlug}/products?category=${cat.slug}`}
              className="group flex flex-col bg-white rounded-xl p-5 shadow-sm hover:shadow-md border border-gray-100 transition-all hover:-translate-y-0.5"
            >
              <h3 className="font-semibold text-sm text-gray-900 group-hover:underline">
                {cat.name}
              </h3>
              {cat.product_count !== undefined && (
                <p className="text-xs mt-1.5" style={{ color: primaryColor }}>
                  {cat.product_count} products
                </p>
              )}
              {cat.description && (
                <p className="text-xs text-gray-400 mt-1 line-clamp-2 leading-relaxed">
                  {cat.description}
                </p>
              )}
            </Link>
          ))}
    </div>
  );
}
