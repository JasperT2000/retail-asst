/**
 * Shared TypeScript interfaces for the Retail AI Store Assistant frontend.
 *
 * Naming convention:
 *   - API response shapes use snake_case to match the Python backend directly.
 *   - ChatMessage is the frontend UI model (adds timestamp).
 *   - ConversationMessage is the API payload shape (sent to the backend).
 */

// ---------------------------------------------------------------------------
// Store & catalogue
// ---------------------------------------------------------------------------

export interface Store {
  slug: string;
  name: string;
  primary_color: string;
  logo_url: string;
  /** Populated by GET /stores (counts from Neo4j) */
  category_count?: number;
  product_count?: number;
  /** Populated by GET /stores/{slug} */
  address?: string;
  phone?: string;
  opening_hours?: Record<string, string>;
}

export interface Category {
  slug: string;
  name: string;
  description: string | null;
  image_url: string | null;
  product_count?: number;
}

export interface AisleLocation {
  location_id?: string;
  aisle: string;
  bay: string;
  section: string;
  floor: string;
  display_label: string;
}

export interface FAQ {
  faq_id?: string;
  question: string;
  answer: string;
}

/** Compact product row — returned by GET /stores/{slug}/products */
export interface ProductListItem {
  slug: string;
  name: string;
  price: number;
  image_url: string | null;
  stock_status: "in_stock" | "low_stock" | "out_of_stock";
  short_description: string | null;
  aisle_label?: string | null;
}

/** Full product — returned by GET /stores/{slug}/products/{slug} */
export interface Product {
  slug: string;
  store_slug: string;
  name: string;
  brand: string;
  model_number: string;
  price: number;
  original_price: number | null;
  description: string;
  short_description: string;
  specifications: Record<string, string> | string;
  image_url: string | null;
  stock_status: "in_stock" | "low_stock" | "out_of_stock";
  stock_quantity: number;
  sku: string;
}

export interface ProductDetail extends Product {
  location: AisleLocation | null;
  faqs: FAQ[];
  compatible_with: Array<{ slug: string; name: string; price: number }>;
  alternatives: Array<{ slug: string; name: string; price: number }>;
}

export interface PolicyDoc {
  policy_id: string;
  policy_type: string;
  title: string;
  summary: string | null;
  content: string;
  last_updated: string;
}

// ---------------------------------------------------------------------------
// Chat
// ---------------------------------------------------------------------------

/** UI model — includes timestamp for display */
export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp: number;
}

/** API payload shape — sent to POST /chat/stream */
export interface ConversationMessage {
  role: "user" | "assistant";
  content: string;
}

/** Metadata emitted after the token stream completes */
export interface ChatMetadata {
  confidence: number;
  sources: string[];
  human_notified: boolean;
  intent: string;
}

// ---------------------------------------------------------------------------
// Store theme
// ---------------------------------------------------------------------------

export interface StoreTheme {
  primary: string;
  background: string;
  text: string;
}

export const STORE_THEMES: Record<string, StoreTheme> = {
  jbhifi: { primary: "#FFD700", background: "#1a1a1a", text: "#1a1a1a" },
  bunnings: { primary: "#E8352A", background: "#ffffff", text: "#ffffff" },
  babybunting: { primary: "#F472B6", background: "#ffffff", text: "#ffffff" },
  supercheapauto: { primary: "#E8352A", background: "#1a1a1a", text: "#ffffff" },
};

export const STORE_NAMES: Record<string, string> = {
  jbhifi: "JB Hi-Fi",
  bunnings: "Bunnings Warehouse",
  babybunting: "Baby Bunting",
  supercheapauto: "Supercheap Auto",
};

export function getStoreTheme(slug: string): StoreTheme {
  return STORE_THEMES[slug] ?? STORE_THEMES["jbhifi"];
}
