"""
Pydantic models for the RAG pipeline.

These models are shared across graph_retriever, vector_retriever,
hybrid_retriever, prompt_builder, and the pipeline orchestrator.
All fields use snake_case. Optional fields default to None or [].
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class StoreInfo(BaseModel):
    """Metadata for a store node retrieved from Neo4j."""

    slug: str
    name: str
    address: str = ""
    phone: str = ""
    opening_hours: dict[str, str] = Field(default_factory=dict)
    primary_color: str = ""
    logo_url: str = ""


class AisleLocationNode(BaseModel):
    """An AisleLocation node from Neo4j."""

    location_id: str = ""
    store_slug: str = ""
    aisle: str = ""
    bay: str = ""
    section: str = ""
    floor: str = ""
    display_label: str = ""


class FAQNode(BaseModel):
    """A FAQ node from Neo4j."""

    faq_id: str = ""
    question: str
    answer: str
    store_slug: str = ""


class ProductNode(BaseModel):
    """A Product node from Neo4j, enriched with optional location and FAQs."""

    slug: str
    store_slug: str = ""
    name: str
    brand: str = ""
    model_number: str = ""
    price: float = 0.0
    original_price: float | None = None
    description: str = ""
    short_description: str = ""
    specifications: dict[str, Any] = Field(default_factory=dict)
    image_url: str = ""
    stock_status: str = "in_stock"
    stock_quantity: int = 0
    sku: str = ""
    location: AisleLocationNode | None = None
    faqs: list[FAQNode] = Field(default_factory=list)


class PolicyDocNode(BaseModel):
    """A PolicyDoc node from Neo4j."""

    policy_id: str
    store_slug: str = ""
    policy_type: str = ""
    title: str
    content: str = ""
    summary: str = ""
    last_updated: str = ""


class RetrievalResult(BaseModel):
    """
    Output of the HybridRetriever.

    Contains structured results from both graph traversal and vector search,
    a formatted context string ready for prompt injection, and metadata about
    retrieval quality.
    """

    graph_context: list[dict[str, Any]] = Field(default_factory=list)
    vector_context: list[dict[str, Any]] = Field(default_factory=list)
    merged_context: str = ""
    confidence_score: float = 0.0
    source_nodes: list[str] = Field(default_factory=list)
    human_escalation_required: bool = False
    escalation_reason: str | None = None


class ChatMessage(BaseModel):
    """A single turn in a conversation."""

    role: str  # "user" | "assistant" | "system"
    content: str


class PipelineOutput(BaseModel):
    """
    Complete output of one RAGPipeline.run() invocation.

    Populated after the streaming generator is exhausted.
    """

    full_response: str = ""
    intent: str = ""
    confidence_score: float = 0.0
    source_nodes: list[str] = Field(default_factory=list)
    human_notified: bool = False
    escalation_reason: str | None = None
    model_used: str = ""
