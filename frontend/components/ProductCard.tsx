"use client";

/**
 * Compact product grid card.
 *
 * Displays product image, name, price, stock status badge, and optional
 * aisle badge. Used in the products listing page and knowledge panel.
 * Clicking navigates to the full product detail page.
 */

import Link from "next/link";
import { MapPin } from "lucide-react";
import type { ProductListItem } from "../lib/types";

interface ProductCardProps {
  product: ProductListItem;
  storeSlug: string;
  primaryColor?: string;
}

const STOCK_STYLES: Record<
  ProductListItem["stock_status"],
  { label: string; classes: string }
> = {
  in_stock: { label: "In Stock", classes: "bg-green-100 text-green-700" },
  low_stock: { label: "Low Stock", classes: "bg-amber-100 text-amber-700" },
  out_of_stock: {
    label: "Out of Stock",
    classes: "bg-red-100 text-red-700",
  },
};

export default function ProductCard({
  product,
  storeSlug,
  primaryColor = "#6366f1",
}: ProductCardProps) {
  const stock = STOCK_STYLES[product.stock_status];

  return (
    <Link
      href={`/${storeSlug}/products/${product.slug}`}
      className="group flex flex-col bg-white rounded-xl border border-gray-100 shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all overflow-hidden"
      aria-label={`View ${product.name} — $${product.price.toFixed(2)}`}
    >
      {/* Image */}
      <div className="w-full h-40 bg-gray-50 flex items-center justify-center p-3 border-b border-gray-100">
        {product.image_url ? (
          <img
            src={product.image_url}
            alt={product.name}
            className="max-h-full max-w-full object-contain"
          />
        ) : (
          <div className="w-16 h-16 rounded-lg bg-gray-200 flex items-center justify-center text-gray-300 text-xs">
            No image
          </div>
        )}
      </div>

      {/* Info */}
      <div className="flex flex-col flex-1 p-4 space-y-2">
        <p className="text-sm font-semibold text-gray-900 line-clamp-2 leading-snug group-hover:underline">
          {product.name}
        </p>

        {product.short_description && (
          <p className="text-xs text-gray-400 line-clamp-2 leading-relaxed">
            {product.short_description}
          </p>
        )}

        <div className="flex-1" />

        {/* Price + stock */}
        <div className="flex items-center justify-between gap-2 pt-1">
          <span
            className="text-base font-bold"
            style={{ color: primaryColor }}
          >
            ${product.price.toFixed(2)}
          </span>
          <span
            className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${stock.classes}`}
          >
            {stock.label}
          </span>
        </div>

        {/* Aisle badge */}
        {product.aisle_label && (
          <div className="flex items-center gap-1 text-[10px] text-gray-400">
            <MapPin className="h-3 w-3 shrink-0" aria-hidden="true" />
            <span className="truncate">{product.aisle_label}</span>
          </div>
        )}
      </div>
    </Link>
  );
}
