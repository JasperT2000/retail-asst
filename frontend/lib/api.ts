/**
 * Backend API client.
 *
 * All requests go through this module. The base URL is controlled exclusively
 * by the NEXT_PUBLIC_BACKEND_URL environment variable.
 */

import type {
  Store,
  Category,
  ProductListItem,
  ProductDetail,
  PolicyDoc,
} from "./types";

const BASE_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`API ${res.status} for ${path}`);
  }
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Stores
// ---------------------------------------------------------------------------

export async function fetchStores(): Promise<Store[]> {
  const data = await apiFetch<{ stores: Store[] }>("/stores");
  return data.stores;
}

export async function fetchStore(storeSlug: string): Promise<Store> {
  return apiFetch<Store>(`/stores/${storeSlug}`);
}

// ---------------------------------------------------------------------------
// Categories
// ---------------------------------------------------------------------------

export async function fetchCategories(storeSlug: string): Promise<Category[]> {
  const data = await apiFetch<{ categories: Category[] }>(
    `/stores/${storeSlug}/categories`
  );
  return data.categories;
}

// ---------------------------------------------------------------------------
// Products
// ---------------------------------------------------------------------------

export interface FetchProductsOptions {
  categorySlug?: string;
  page?: number;
  pageSize?: number;
}

export interface ProductsPage {
  products: ProductListItem[];
  total: number;
  page: number;
  page_size: number;
}

export async function fetchProducts(
  storeSlug: string,
  options: FetchProductsOptions = {}
): Promise<ProductsPage> {
  const params = new URLSearchParams();
  if (options.categorySlug) params.set("category_slug", options.categorySlug);
  if (options.page) params.set("page", String(options.page));
  if (options.pageSize) params.set("page_size", String(options.pageSize));

  const query = params.toString();
  return apiFetch<ProductsPage>(
    `/stores/${storeSlug}/products${query ? `?${query}` : ""}`
  );
}

export async function fetchProduct(
  storeSlug: string,
  productSlug: string
): Promise<ProductDetail> {
  const raw = await apiFetch<{
    product: Record<string, unknown>;
    location: Record<string, unknown> | null;
    faqs: Array<Record<string, unknown>>;
    compatible_with: Array<{ slug: string; name: string; price: number }>;
    alternatives: Array<{ slug: string; name: string; price: number }>;
  }>(`/stores/${storeSlug}/products/${productSlug}`);

  // Normalise the Neo4j node dict into a typed ProductDetail
  return {
    ...(raw.product as unknown as ProductDetail),
    location: raw.location as ProductDetail["location"],
    faqs: raw.faqs as ProductDetail["faqs"],
    compatible_with: raw.compatible_with,
    alternatives: raw.alternatives,
  };
}

// ---------------------------------------------------------------------------
// Policies
// ---------------------------------------------------------------------------

export async function fetchPolicies(storeSlug: string): Promise<PolicyDoc[]> {
  const data = await apiFetch<{ policies: PolicyDoc[] }>(
    `/stores/${storeSlug}/policies`
  );
  return data.policies;
}
