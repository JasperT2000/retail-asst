# DATA_SCHEMA.md — Graph Model & Data Structures
> Claude Code: Read this alongside MASTER_SPEC.md when working on ingestion, graph setup, or RAG retrieval.

---

## Neo4j Graph Model

### Node Types

#### `Store`
```
Properties:
  - slug: String (unique) e.g. "jbhifi"
  - name: String e.g. "JB Hi-Fi"
  - address: String e.g. "Sample Store, Melbourne VIC"
  - phone: String
  - opening_hours: String (JSON stringified map)
  - primary_color: String (hex)
  - logo_url: String
```

#### `Category`
```
Properties:
  - slug: String (unique within store) e.g. "jbhifi-laptops"
  - name: String e.g. "Laptops"
  - description: String
  - store_slug: String (denormalised for fast filtering)
  - image_url: String
  - embedding: List<Float> (1536-dim, text-embedding-3-small)
```

#### `Product`
```
Properties:
  - slug: String (unique) e.g. "jbhifi-sony-wh1000xm5"
  - store_slug: String
  - name: String
  - brand: String
  - model_number: String
  - price: Float
  - original_price: Float (for sale items)
  - description: String (long form)
  - short_description: String (1–2 sentences)
  - specifications: String (JSON stringified map)
  - image_url: String
  - stock_status: String ("in_stock" | "low_stock" | "out_of_stock")
  - stock_quantity: Integer (simulated)
  - sku: String
  - embedding: List<Float> (1536-dim — embeds name + short_description + specs summary)
```

#### `AisleLocation`
```
Properties:
  - location_id: String (unique) e.g. "jbhifi-aisle-3-bay-12"
  - store_slug: String
  - aisle: String e.g. "Aisle 3"
  - bay: String e.g. "Bay 12"
  - section: String e.g. "Headphones & Audio"
  - floor: String e.g. "Ground Floor"
  - display_label: String e.g. "Aisle 3, Bay 12 — Headphones"
```

#### `PolicyDoc`
```
Properties:
  - policy_id: String (unique) e.g. "jbhifi-returns"
  - store_slug: String
  - policy_type: String ("returns" | "warranty" | "price_match" | "loyalty" | "layby" | "delivery" | "privacy" | "trade_in")
  - title: String
  - content: String (full policy text)
  - summary: String (2–3 sentence summary)
  - last_updated: String
  - embedding: List<Float> (1536-dim — embeds title + content)
```

#### `FAQ`
```
Properties:
  - faq_id: String (unique) e.g. "jbhifi-sony-wh1000xm5-faq-1"
  - question: String
  - answer: String
  - store_slug: String
  - embedding: List<Float> (1536-dim — embeds question + answer)
```

#### `Brand`
```
Properties:
  - slug: String (unique) e.g. "sony"
  - name: String
  - description: String
  - logo_url: String
```

---

### Relationships

```cypher
// Store → Category
(Store)-[:HAS_CATEGORY]->(Category)

// Category → Product
(Category)-[:CONTAINS]->(Product)

// Product → Location
(Product)-[:LOCATED_AT]->(AisleLocation)

// Product → FAQ
(Product)-[:HAS_FAQ]->(FAQ)

// Store → PolicyDoc
(Store)-[:HAS_POLICY]->(PolicyDoc)

// Category → PolicyDoc (e.g. power tools have specific return rules)
(Category)-[:HAS_POLICY]->(PolicyDoc)

// Product → Brand
(Product)-[:MADE_BY]->(Brand)

// Product → Product (accessories)
(Product)-[:COMPATIBLE_WITH]->(Product)

// Product → Product (alternatives)
(Product)-[:ALTERNATIVE_TO]->(Product)

// Product → Product (frequently bought together)
(Product)-[:BOUGHT_WITH]->(Product)
```

---

### Vector Indexes (Neo4j vector index — create on ingestion)

```cypher
CREATE VECTOR INDEX product_embedding IF NOT EXISTS
FOR (p:Product) ON (p.embedding)
OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}};

CREATE VECTOR INDEX category_embedding IF NOT EXISTS
FOR (c:Category) ON (c.embedding)
OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}};

CREATE VECTOR INDEX policy_embedding IF NOT EXISTS
FOR (d:PolicyDoc) ON (d.embedding)
OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}};

CREATE VECTOR INDEX faq_embedding IF NOT EXISTS
FOR (f:FAQ) ON (f.embedding)
OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}};
```

---

### Unique Constraints

```cypher
CREATE CONSTRAINT store_slug_unique IF NOT EXISTS FOR (s:Store) REQUIRE s.slug IS UNIQUE;
CREATE CONSTRAINT product_slug_unique IF NOT EXISTS FOR (p:Product) REQUIRE p.slug IS UNIQUE;
CREATE CONSTRAINT category_slug_unique IF NOT EXISTS FOR (c:Category) REQUIRE c.slug IS UNIQUE;
CREATE CONSTRAINT policy_id_unique IF NOT EXISTS FOR (d:PolicyDoc) REQUIRE d.policy_id IS UNIQUE;
CREATE CONSTRAINT faq_id_unique IF NOT EXISTS FOR (f:FAQ) REQUIRE f.faq_id IS UNIQUE;
CREATE CONSTRAINT location_id_unique IF NOT EXISTS FOR (l:AisleLocation) REQUIRE l.location_id IS UNIQUE;
```

---

## Processed Data JSON Format

Each store has a single `processed/{store_slug}.json` file with this structure:

```json
{
  "store": {
    "slug": "jbhifi",
    "name": "JB Hi-Fi",
    "address": "Level 1, Melbourne Central, 211 La Trobe St, Melbourne VIC 3000",
    "phone": "03 9669 3500",
    "opening_hours": {
      "monday": "9:00am - 7:00pm",
      "tuesday": "9:00am - 7:00pm",
      "wednesday": "9:00am - 7:00pm",
      "thursday": "9:00am - 9:00pm",
      "friday": "9:00am - 9:00pm",
      "saturday": "9:00am - 7:00pm",
      "sunday": "10:00am - 7:00pm"
    },
    "primary_color": "#FFD700",
    "logo_url": "/logos/jbhifi.png"
  },
  "categories": [
    {
      "slug": "jbhifi-laptops",
      "name": "Laptops",
      "description": "Browse our range of laptops from Apple, Dell, HP, Lenovo and more.",
      "image_url": "/categories/jbhifi-laptops.jpg"
    }
  ],
  "products": [
    {
      "slug": "jbhifi-apple-macbook-air-m3-13",
      "category_slug": "jbhifi-laptops",
      "name": "Apple MacBook Air 13-inch (M3)",
      "brand": "Apple",
      "model_number": "MRXN3X/A",
      "price": 1699.00,
      "original_price": null,
      "description": "The MacBook Air with M3 chip delivers...",
      "short_description": "Apple MacBook Air 13-inch with M3 chip, 8GB RAM, 256GB SSD in Midnight.",
      "specifications": {
        "Chip": "Apple M3",
        "RAM": "8GB unified memory",
        "Storage": "256GB SSD",
        "Display": "13.6-inch Liquid Retina",
        "Battery": "Up to 18 hours",
        "Weight": "1.24 kg",
        "Colour": "Midnight"
      },
      "image_url": "/products/jbhifi-apple-macbook-air-m3-13.jpg",
      "stock_status": "in_stock",
      "stock_quantity": 12,
      "sku": "JB-APL-MBA13M3-MID",
      "aisle_location": {
        "aisle": "Aisle 2",
        "bay": "Bay 4",
        "section": "Apple Products",
        "floor": "Ground Floor",
        "display_label": "Aisle 2, Bay 4 — Apple Products"
      },
      "faqs": [
        {
          "question": "Does the MacBook Air M3 support external monitors?",
          "answer": "Yes, the MacBook Air M3 supports one external display up to 6K resolution at 60Hz via Thunderbolt/USB-C. When the laptop lid is closed, it can support one external display."
        },
        {
          "question": "Is the RAM upgradeable on the MacBook Air M3?",
          "answer": "No, the RAM is integrated into the M3 chip and cannot be upgraded after purchase. We recommend choosing 16GB if you plan to run multiple applications simultaneously."
        },
        {
          "question": "What is JB Hi-Fi's return policy for MacBooks?",
          "answer": "MacBooks can be returned within 30 days of purchase if unopened. Opened items can be exchanged or returned under JB Hi-Fi's change-of-mind policy within 10 days with original packaging."
        }
      ],
      "compatible_with": [
        "jbhifi-apple-usbc-hub-7in1",
        "jbhifi-apple-magic-mouse",
        "jbhifi-apple-magic-keyboard"
      ],
      "alternatives": [
        "jbhifi-dell-xps-13-plus",
        "jbhifi-lenovo-yoga-9i"
      ]
    }
  ],
  "policies": [
    {
      "policy_id": "jbhifi-returns",
      "policy_type": "returns",
      "title": "JB Hi-Fi Returns & Refunds Policy",
      "content": "Full policy text here...",
      "summary": "JB Hi-Fi offers a 30-day return policy on unopened items and 10-day change-of-mind returns on opened items with original packaging. Faulty items are covered under Australian Consumer Law.",
      "last_updated": "2024-01-01"
    }
  ]
}
```

---

## Category Structure Per Store

### JB Hi-Fi (100 products across 8 categories)
| Category | Slug | Products |
|---|---|---|
| Laptops & Computers | jbhifi-laptops | 13 |
| TVs & Displays | jbhifi-tvs | 13 |
| Headphones & Audio | jbhifi-audio | 12 |
| Mobile Phones | jbhifi-mobiles | 12 |
| Gaming | jbhifi-gaming | 12 |
| Cameras & Photography | jbhifi-cameras | 12 |
| Tablets & E-Readers | jbhifi-tablets | 13 |
| Smart Home & Wearables | jbhifi-wearables | 13 |

### Bunnings (100 products across 8 categories)
| Category | Slug | Products |
|---|---|---|
| Power Tools | bunnings-power-tools | 14 |
| Hand Tools | bunnings-hand-tools | 12 |
| Garden & Outdoor | bunnings-garden | 14 |
| Paint & Decorating | bunnings-paint | 12 |
| Plumbing | bunnings-plumbing | 12 |
| Lighting | bunnings-lighting | 12 |
| Storage & Organisation | bunnings-storage | 12 |
| Building & Flooring | bunnings-building | 12 |

### Baby Bunting (100 products across 7 categories)
| Category | Slug | Products |
|---|---|---|
| Prams & Strollers | babybunting-prams | 15 |
| Car Seats | babybunting-carseats | 14 |
| Feeding & Nursing | babybunting-feeding | 14 |
| Nursery & Furniture | babybunting-nursery | 15 |
| Safety & Monitors | babybunting-safety | 14 |
| Clothing & Accessories | babybunting-clothing | 14 |
| Toys & Play | babybunting-toys | 14 |

### Supercheap Auto (100 products across 7 categories)
| Category | Slug | Products |
|---|---|---|
| Car Care & Cleaning | supercheapauto-carcare | 15 |
| Batteries & Electrical | supercheapauto-batteries | 14 |
| Car Audio & Tech | supercheapauto-audio | 15 |
| Tools & Equipment | supercheapauto-tools | 14 |
| Oils & Fluids | supercheapauto-oils | 14 |
| Towing & Trailer | supercheapauto-towing | 14 |
| Camping & Adventure | supercheapauto-camping | 14 |

---

## Embedding Strategy

| Node | Text to embed | Rationale |
|---|---|---|
| Product | `{name}. {brand}. {short_description}. Specs: {top 5 specs}` | Captures searchable identity |
| Category | `{name}. {description}` | Enables category-level semantic search |
| PolicyDoc | `{title}. {content}` | Full policy for accurate retrieval |
| FAQ | `{question} {answer}` | Question-answer pairs for direct retrieval |

---

## Graph Cypher Query Examples (for retrieval reference)

### Find product + location + FAQs
```cypher
MATCH (s:Store {slug: $store_slug})-[:HAS_CATEGORY]->(c:Category)-[:CONTAINS]->(p:Product {slug: $product_slug})
OPTIONAL MATCH (p)-[:LOCATED_AT]->(l:AisleLocation)
OPTIONAL MATCH (p)-[:HAS_FAQ]->(f:FAQ)
RETURN p, l, collect(f) as faqs
```

### Find compatible accessories
```cypher
MATCH (p:Product {slug: $product_slug})-[:COMPATIBLE_WITH]->(acc:Product)
RETURN acc.name, acc.price, acc.slug
```

### Find alternatives under a price
```cypher
MATCH (p:Product {slug: $product_slug})-[:ALTERNATIVE_TO]->(alt:Product)
WHERE alt.price <= $max_price
RETURN alt.name, alt.price, alt.short_description
ORDER BY alt.price ASC
```

### Find store policy by type
```cypher
MATCH (s:Store {slug: $store_slug})-[:HAS_POLICY]->(pol:PolicyDoc {policy_type: $policy_type})
RETURN pol.title, pol.content, pol.summary
```

### Vector search for products (semantic)
```cypher
CALL db.index.vector.queryNodes('product_embedding', $top_k, $query_embedding)
YIELD node AS p, score
WHERE p.store_slug = $store_slug
RETURN p.name, p.slug, p.short_description, p.price, score
ORDER BY score DESC
```

---

## Eval Dataset Format (`eval/eval_dataset.json`)

```json
[
  {
    "id": "eval-001",
    "store_slug": "jbhifi",
    "question": "Where can I find Sony headphones in the store?",
    "ground_truth": "Sony headphones are located in Aisle 3, Bay 12 in the Headphones & Audio section on the Ground Floor.",
    "expected_intent": "location",
    "expected_nodes": ["Product", "AisleLocation"],
    "difficulty": "easy"
  },
  {
    "id": "eval-002",
    "store_slug": "bunnings",
    "question": "What is the return policy for power tools?",
    "ground_truth": "Bunnings offers a 30-day return policy on power tools with proof of purchase...",
    "expected_intent": "policy",
    "expected_nodes": ["PolicyDoc"],
    "difficulty": "medium"
  },
  {
    "id": "eval-003",
    "store_slug": "jbhifi",
    "question": "I'm looking for a laptop under $1500 that's good for video editing",
    "ground_truth": "...",
    "expected_intent": "recommendation",
    "expected_nodes": ["Product", "Category"],
    "difficulty": "hard"
  }
]
```

Eval set must contain 50 questions:
- 15 easy (direct product/location lookup)
- 20 medium (policy, category, availability)
- 15 hard (recommendations, comparisons, multi-hop graph)
- Spread across all 4 stores (~12-13 per store)
