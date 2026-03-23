"use client";

/**
 * Persistent layout for all store-scoped pages.
 *
 * Renders a fixed top navigation bar with the store's brand colour,
 * nav links (Ask AI / Products / Policies), and a mobile hamburger menu.
 * The nav height (3.5rem / 56px) is offset by pt-14 on the content div.
 */

import { useState } from "react";
import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { Menu, X, ChevronLeft } from "lucide-react";
import { STORE_THEMES, STORE_NAMES } from "../../lib/types";

export default function StoreLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const params = useParams();
  const slug = (params.store as string) ?? "";
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);

  const theme = STORE_THEMES[slug] ?? STORE_THEMES["jbhifi"];
  const storeName = STORE_NAMES[slug] ?? slug;

  const navLinks = [
    { href: `/${slug}`, label: "Ask AI" },
    { href: `/${slug}/products`, label: "Products" },
    { href: `/${slug}/policies`, label: "Policies" },
  ];

  const isActive = (href: string) => pathname === href;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Fixed top nav */}
      <nav
        className="fixed top-0 left-0 right-0 z-50 shadow-sm"
        style={{ backgroundColor: theme.primary }}
        aria-label="Store navigation"
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
          {/* Logo / store name */}
          <Link
            href={`/${slug}`}
            className="flex items-center gap-2.5 font-bold text-base shrink-0"
            style={{ color: theme.text }}
          >
            {storeName}
            <span
              className="hidden sm:inline text-[9px] font-semibold border rounded px-1.5 py-0.5 tracking-wider"
              style={{
                borderColor: `${theme.text}35`,
                color: theme.text,
                opacity: 0.7,
              }}
            >
              AI ASSISTANT
            </span>
          </Link>

          {/* Desktop nav links */}
          <div className="hidden md:flex items-center gap-1">
            {navLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="px-4 py-1.5 rounded-full text-sm font-medium transition-all"
                style={{
                  color: theme.text,
                  backgroundColor: isActive(link.href)
                    ? `${theme.text}18`
                    : "transparent",
                  opacity: isActive(link.href) ? 1 : 0.7,
                }}
              >
                {link.label}
              </Link>
            ))}

            <Link
              href="/"
              className="ml-4 flex items-center gap-1 text-xs transition-opacity hover:opacity-80"
              style={{ color: theme.text, opacity: 0.5 }}
            >
              <ChevronLeft className="h-3 w-3" aria-hidden="true" />
              All stores
            </Link>
          </div>

          {/* Mobile hamburger */}
          <button
            className="md:hidden p-1 rounded"
            style={{ color: theme.text }}
            onClick={() => setMenuOpen((v) => !v)}
            aria-label={menuOpen ? "Close menu" : "Open menu"}
            aria-expanded={menuOpen}
          >
            {menuOpen ? (
              <X className="h-6 w-6" aria-hidden="true" />
            ) : (
              <Menu className="h-6 w-6" aria-hidden="true" />
            )}
          </button>
        </div>

        {/* Mobile dropdown */}
        {menuOpen && (
          <div
            className="md:hidden border-t"
            style={{
              backgroundColor: theme.primary,
              borderColor: `${theme.text}20`,
            }}
          >
            <div className="px-4 py-3 space-y-1">
              {navLinks.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className="block py-2.5 px-3 rounded-lg text-sm font-medium"
                  style={{
                    color: theme.text,
                    backgroundColor: isActive(link.href)
                      ? `${theme.text}15`
                      : "transparent",
                  }}
                  onClick={() => setMenuOpen(false)}
                >
                  {link.label}
                </Link>
              ))}
              <Link
                href="/"
                className="block py-2 px-3 text-xs"
                style={{ color: theme.text, opacity: 0.5 }}
                onClick={() => setMenuOpen(false)}
              >
                ← All stores
              </Link>
            </div>
          </div>
        )}
      </nav>

      {/* Page content — offset by nav height */}
      <div className="pt-14">{children}</div>
    </div>
  );
}
