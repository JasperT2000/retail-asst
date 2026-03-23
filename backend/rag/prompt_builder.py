"""
LLM prompt construction.

Builds the system prompt from store metadata and retrieved context,
then assembles the full messages list (system + history + user with context).
All prompts use Australian English spelling.
"""

from __future__ import annotations

import json

import structlog

from backend.rag.models import RetrievalResult, StoreInfo

log = structlog.get_logger(__name__)

_STORE_NAMES = {
    "jbhifi": "JB Hi-Fi",
    "bunnings": "Bunnings Warehouse",
    "babybunting": "Baby Bunting",
    "supercheapauto": "Supercheap Auto",
}

_SYSTEM_TEMPLATE = """\
You are a sharp, friendly AI store assistant for {store_name}.

Store details:
  Address: {address}
  Phone: {phone}
  Opening hours: {opening_hours}

Always use Australian English spelling (e.g. "colour", "catalogue", "organise").
Base every answer strictly on the context provided below. If the information \
isn't there, say you're not sure and offer to connect the customer with a staff member.

Response style — adapt to the customer's intent:
- **product_info / recommendation**: 2–3 sentences max. Name the product and \
  key specs in plain language. If it's genuinely impressive (e.g. exceptional \
  value, award-winning, unique feature), mention it naturally — never push \
  something that isn't backed by the data.
- **stock**: One direct sentence — in stock or not, and quantity if known.
- **location**: One sentence with the exact aisle and bay number. \
  Only include location details when the customer is asking where to find something.
- **price**: State the price clearly. Add a brief comparison if an alternative \
  is a notably better deal.
- **policy**: Summarise the key rule in 1–2 sentences. Avoid quoting policy \
  verbatim unless the customer specifically asks.
- **escalation**: Let the customer know a staff member has been notified and \
  will assist shortly — keep it warm and brief.
- **general**: Answer directly in 1–2 sentences.

Never volunteer aisle/bay numbers unless the customer is asking for location. \
Never pad answers with store address or hours unless explicitly asked.

Retrieved context:
{context}
"""


class PromptBuilder:
    """Builds structured LLM prompts from store info and retrieval results."""

    def build_system_prompt(
        self, store_slug: str, store_info: StoreInfo | None
    ) -> str:
        """
        Build the system prompt including store metadata and retrieved context.

        Args:
            store_slug: Active store identifier (used as fallback if store_info is None).
            store_info: Store node data from Neo4j.

        Returns:
            Formatted system prompt string.
        """
        store_name = _STORE_NAMES.get(store_slug, store_slug)
        address = ""
        phone = ""
        opening_hours_str = ""

        if store_info:
            store_name = store_info.name or store_name
            address = store_info.address
            phone = store_info.phone
            hours = store_info.opening_hours
            if hours:
                lines = [
                    f"  {day.capitalize()}: {time}"
                    for day, time in hours.items()
                ]
                opening_hours_str = "\n".join(lines)
            else:
                opening_hours_str = "See store website for current hours."

        # Placeholder — context injected in build_user_prompt
        return _SYSTEM_TEMPLATE.format(
            store_name=store_name,
            address=address or "See store website",
            phone=phone or "See store website",
            opening_hours=opening_hours_str or "See store website",
            context="{context}",  # replaced per-request in build_user_prompt
        )

    def build_user_prompt(
        self,
        query: str,
        retrieval_result: RetrievalResult,
        conversation_history: list[dict[str, str]],
        store_slug: str = "",
        store_info: StoreInfo | None = None,
        intent: str = "general",
    ) -> list[dict[str, str]]:
        """
        Assemble the full messages list for the LLM.

        The system message has the retrieved context injected.
        Conversation history follows, then the current user query.

        Args:
            query: Current user query.
            retrieval_result: Merged retrieval context.
            conversation_history: Prior turns as list of {role, content} dicts.
            store_slug: Active store identifier.
            store_info: Store node data (optional, for richer system prompt).
            intent: Classified intent — used to set the response style hint.

        Returns:
            List of {role, content} message dicts ready for the LLM client.
        """
        context_text = self._format_context(retrieval_result)

        # Build system prompt with context substituted in
        system_template = self.build_system_prompt(store_slug, store_info)
        system_content = system_template.replace("{context}", context_text)

        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_content}
        ]

        # Inject conversation history (cap at last 10 turns to stay within context)
        for turn in conversation_history[-10:]:
            messages.append({"role": turn["role"], "content": turn["content"]})

        # Prepend an intent hint to the user query so the model can calibrate length
        intent_hint = f"[Intent: {intent}] " if intent and intent != "general" else ""
        messages.append({"role": "user", "content": f"{intent_hint}{query}"})

        log.debug(
            "prompt_builder.built",
            store=store_slug,
            context_len=len(context_text),
            history_turns=len(conversation_history),
            total_messages=len(messages),
        )

        return messages

    def _format_context(self, retrieval_result: RetrievalResult) -> str:
        """
        Format the merged retrieval context into a clean text block.

        Prefers the pre-formatted merged_context string from the retriever.
        Falls back to formatting graph_context and vector_context directly.

        Args:
            retrieval_result: Output from HybridRetriever.

        Returns:
            Formatted context string for prompt injection.
        """
        if retrieval_result.merged_context:
            return retrieval_result.merged_context

        # Fallback: manually format from raw contexts
        all_nodes = retrieval_result.graph_context + retrieval_result.vector_context
        if not all_nodes:
            return "No relevant context was retrieved."

        parts: list[str] = []
        seen: set[str] = set()

        for node in all_nodes[:8]:
            node_id = str(
                node.get("slug") or node.get("policy_id") or node.get("faq_id") or ""
            )
            if node_id in seen:
                continue
            seen.add(node_id)

            if node.get("slug") and node.get("price") is not None:
                qty = node.get("stock_quantity")
                stock_str = node.get("stock_status", "unknown")
                if qty is not None:
                    stock_str += f" ({qty} units)"
                parts.append(
                    f"PRODUCT: {node.get('name')} "
                    f"(${node.get('price')}) | "
                    f"Stock: {stock_str} | "
                    f"{node.get('short_description', '')}"
                )
            elif node.get("policy_id"):
                parts.append(
                    f"POLICY: {node.get('title')} — "
                    f"{node.get('summary', node.get('content', '')[:200])}"
                )
            elif node.get("faq_id"):
                parts.append(
                    f"FAQ: Q: {node.get('question')} A: {node.get('answer')}"
                )

        return "\n".join(parts) or "No relevant context was retrieved."
