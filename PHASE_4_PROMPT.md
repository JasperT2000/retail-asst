# PHASE 4 PROMPT — Next.js Frontend
> Copy this entire prompt into Claude Code. Requires Phase 3 to be complete and running.

---

## Instructions for Claude Code

Read `MASTER_SPEC.md` in full, paying close attention to the Frontend UX Requirements and Store Theme Colours sections.

You are building the complete Next.js 14 frontend with App Router, TypeScript, and Tailwind CSS. This app will be used for LinkedIn demos — it must look genuinely professional and polished, not like a template.

---

## Design Principles

- Clean, modern retail-app aesthetic
- Each store has its own branded theme colour (see MASTER_SPEC.md)
- Mobile-first responsive design (users may scan QR code on phone)
- Chat interface must feel instant — tokens stream in as they arrive
- Product pages must look like actual retail product pages

---

## Deliverables

### 1. Project Setup

`frontend/package.json` — dependencies:
- `next@14`
- `react@18`, `react-dom@18`
- `typescript`
- `tailwindcss`, `postcss`, `autoprefixer`
- `@tailwindcss/typography`
- `lucide-react` (icons)
- `framer-motion` (animations)
- `clsx` (conditional classnames)
- `zustand` (lightweight state management for chat history)

### 2. `frontend/lib/types.ts`

Define all shared TypeScript interfaces:
```typescript
interface Store { slug, name, primaryColor, logoUrl, address, phone, openingHours }
interface Category { slug, name, description, imageUrl, productCount }
interface Product { slug, name, brand, price, originalPrice, shortDescription, description, specifications, imageUrl, stockStatus, stockQuantity, aisleLocation, faqs, compatibleWith, alternatives }
interface AisleLocation { aisle, bay, section, floor, displayLabel }
interface FAQ { question, answer }
interface ChatMessage { role: 'user' | 'assistant', content, timestamp }
interface StreamMetadata { confidence, sources, humanNotified, intent }
```

### 3. `frontend/lib/api.ts`

API client functions:
- `getStores(): Promise<Store[]>`
- `getStore(slug): Promise<Store>`
- `getCategories(storeSlug): Promise<Category[]>`
- `getProducts(storeSlug, options?): Promise<Product[]>`
- `getProduct(storeSlug, productSlug): Promise<Product>`

All use `NEXT_PUBLIC_BACKEND_URL` env var. Handle errors gracefully.

### 4. `frontend/lib/sse.ts`

SSE streaming handler:
```typescript
async function* streamChat(
  storeSlug: string,
  message: string,
  sessionId: string,
  history: ChatMessage[]
): AsyncGenerator<{ type: 'token' | 'metadata' | 'done' | 'error', data: any }>
```

Parse SSE events correctly. Handle connection drops with auto-reconnect (max 2 retries).

### 5. Landing Page — `frontend/app/page.tsx`

Store selector page. Design:
- Full-height hero section with tagline: *"Your AI store assistant. Ask anything."*
- 2x2 grid of store cards (desktop), stacked on mobile
- Each card: store logo, store name, category count, product count, branded accent colour
- Hover effect: card lifts with shadow, subtle colour fill
- Click → navigate to `/[store_slug]`
- Clean sans-serif typography throughout

### 6. Store Layout — `frontend/app/[store]/layout.tsx`

Persistent layout for all store pages:
- Top navigation bar with store logo + name + primary colour
- Nav links: "Ask AI", "Products", "Policies"
- Mobile hamburger menu
- Store context provided via Zustand store (so chat page knows which store is active)

### 7. Chat Interface Page — `frontend/app/[store]/page.tsx`

This is the main demo page. Two-column layout on desktop, single column on mobile.

**Left column (60%) — Chat:**
- Message thread with user messages (right-aligned, coloured bubble) and assistant messages (left-aligned, white bubble)
- Streaming text renders token by token with a blinking cursor while streaming
- Message timestamps
- Auto-scroll to latest message
- Input area at bottom: text field + Send button + Mic button
- When human is notified: subtle amber banner appears above input: *"A team member has been notified to assist"*
- Session ID displayed in footer (small, subtle) — useful for LinkedIn demo

**Right column (40%) — Knowledge Panel:**
- Tabs: "Products", "Categories", "Policies"
- Shows browsable store content alongside chat
- Clicking a product in the panel pre-fills chat with: *"Tell me about [product name]"*
- On mobile: knowledge panel collapses, accessible via bottom sheet

### 8. Voice Components

`frontend/components/VoiceInput.tsx`
- Mic button with animated waveform (CSS animation) while recording
- Uses `window.SpeechRecognition` / `window.webkitSpeechRecognition`
- Shows "Listening..." text while active
- On recognition result: populate input field and auto-submit
- Handle browsers that don't support Web Speech API gracefully (hide button)

`frontend/components/VoiceOutput.tsx`
- Auto-reads assistant messages aloud after streaming completes using `window.speechSynthesis`
- Toggle button (speaker icon) to enable/disable voice output
- Respects user preference stored in localStorage

### 9. Product Pages

`frontend/app/[store]/products/page.tsx`
- Category filter tabs at top
- Grid of ProductCard components (3 cols desktop, 2 cols tablet, 1 col mobile)
- Each ProductCard: product image, name, price, stock badge, aisle badge

`frontend/app/[store]/products/[slug]/page.tsx`
- Product detail page — looks like a real retail product page
- Large product image on left
- Name, brand, price (strike-through original price if on sale), stock status badge on right
- Aisle location card with map-pin icon: *"Find it in store: Aisle 3, Bay 12"*
- Specifications table (collapsible on mobile)
- FAQ accordion section
- Compatible accessories horizontal scroll row
- Alternatives grid
- *"Ask AI about this product"* button → opens chat with product pre-queried

`frontend/app/[store]/policies/page.tsx`
- Policy cards grid
- Each card: policy type icon, title, summary, expandable full text

### 10. Component: `MessageBubble.tsx`

- User bubble: right-aligned, store primary colour background
- Assistant bubble: left-aligned, white background with subtle border
- Streaming bubble: shows blinking cursor `▋` at end while tokens arrive
- Confidence indicator: small coloured dot on assistant messages (green ≥ 0.8, amber 0.65–0.8, red < 0.65)
- Source tags: small chips below message showing what was retrieved (e.g. "Product • Policy")

### 11. `frontend/components/StoreSelector.tsx`

Reusable component used on landing page. Props: `stores: Store[]`, `onSelect: (slug) => void`.

---

## Store Theming

Implement a `useStoreTheme(slug)` hook that returns CSS variables:
```typescript
const themes = {
  jbhifi: { primary: '#FFD700', background: '#1a1a1a', text: '#ffffff' },
  bunnings: { primary: '#E8352A', background: '#ffffff', text: '#1a1a1a' },
  babybunting: { primary: '#F472B6', background: '#ffffff', text: '#1a1a1a' },
  supercheapauto: { primary: '#E8352A', background: '#1a1a1a', text: '#ffffff' },
}
```
Apply as CSS custom properties on the store layout root element.

---

## State Management (Zustand)

`frontend/lib/store.ts` — Zustand store:
```typescript
interface AppState {
  currentStore: Store | null
  chatHistory: ChatMessage[]
  isStreaming: boolean
  streamMetadata: StreamMetadata | null
  humanNotified: boolean
  voiceEnabled: boolean
  sessionId: string
  setStore, addMessage, setStreaming, setMetadata, setHumanNotified, toggleVoice, clearHistory
}
```

---

## Constraints

- TypeScript strict mode — no `any` types
- All components must be properly typed
- No inline styles — use Tailwind classes only
- SSE connection must be cancelled when component unmounts
- Accessible: proper `aria-label` on icon buttons, keyboard navigable
- `NEXT_PUBLIC_BACKEND_URL` must be the only place the API URL is referenced
- Loading states on every data fetch (skeleton loaders, not spinners)

---

## Test

```bash
cd frontend
npm install
echo "NEXT_PUBLIC_BACKEND_URL=http://localhost:8000" > .env.local
npm run dev
```

Navigate to `http://localhost:3000`.
- Landing page shows 4 store cards
- Click JB Hi-Fi → chat interface loads with JB branding
- Type "Where are the Sony headphones?" → tokens stream in real time
- Products tab shows product grid
- Click a product → product detail page renders correctly
- Mic button appears and activates voice input
