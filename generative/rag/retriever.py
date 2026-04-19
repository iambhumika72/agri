from __future__ import annotations

"""
generative/rag/retriever.py
==============================
Retrieval-Augmented Generation (RAG) retriever for AgriSense.
Enriches LLM prompts with relevant agronomic knowledge snippets.
"""

import logging
from typing import List, Optional

from .vectorstore import AgriVectorStore, get_vector_store, seed_knowledge_base

log = logging.getLogger(__name__)

_MAX_CONTEXT_CHARS = 1200  # ~300 tokens — safe budget within 4K context window


class AgriRetriever:
    """
    Retrieves relevant agricultural knowledge snippets from the vector store
    and formats them as context for LLM prompts.
    """

    def __init__(self, store: Optional[AgriVectorStore] = None, top_k: int = 3) -> None:
        self.store = store or get_vector_store()
        self.top_k = top_k

        # Seed knowledge base if the store is empty
        if not self.store.documents:
            log.info("Knowledge base empty — seeding with baseline agricultural knowledge.")
            seed_knowledge_base(self.store)

    def retrieve(self, query: str) -> str:
        """
        Retrieves top_k relevant documents for a query and returns them
        as a formatted string ready to be injected into an LLM prompt.

        Parameters
        ----------
        query : str — the farm situation or question to retrieve context for

        Returns
        -------
        str — a multi-line formatted context block, or empty string if no docs
        """
        results = self.store.search(query, top_k=self.top_k)
        if not results:
            return ""

        lines = ["### Relevant Agricultural Knowledge"]
        total_chars = 0
        for i, (doc, score) in enumerate(results, 1):
            snippet = doc[:400]  # cap per-snippet length
            line = f"{i}. {snippet}"
            if total_chars + len(line) > _MAX_CONTEXT_CHARS:
                break
            lines.append(line)
            total_chars += len(line)

        context = "\n".join(lines)
        log.info("Retrieved %d knowledge snippets (%d chars) for query: '%s...'",
                 len(results), total_chars, query[:50])
        return context

    def retrieve_for_irrigation(self, crop_type: str, soil_moisture: float) -> str:
        """Builds a targeted irrigation knowledge query."""
        query = f"How to irrigate {crop_type}? Soil moisture is {soil_moisture:.1f}%."
        return self.retrieve(query)

    def retrieve_for_pest(self, crop_type: str, growth_stage: str, likely_cause: str) -> str:
        """Builds a targeted pest/disease knowledge query."""
        query = f"{crop_type} {growth_stage} stage {likely_cause} pest disease management."
        return self.retrieve(query)

    def retrieve_for_yield(self, crop_type: str, season: str) -> str:
        """Builds a targeted yield knowledge query."""
        query = f"{crop_type} yield {season} season India target improvement."
        return self.retrieve(query)

    def enrich_prompt(self, base_prompt: str, crop_type: str, topic: str = "general") -> str:
        """
        Prepends relevant knowledge context to a prompt.

        Parameters
        ----------
        base_prompt : str — the original user prompt
        crop_type : str — crop for query refinement
        topic : str — one of 'irrigation', 'pest', 'yield', 'general'

        Returns
        -------
        str — enriched prompt with knowledge context prepended
        """
        if topic == "irrigation":
            context = self.retrieve(f"{crop_type} irrigation water requirement schedule")
        elif topic == "pest":
            context = self.retrieve(f"{crop_type} pest disease identification management")
        elif topic == "yield":
            context = self.retrieve(f"{crop_type} yield improvement India best practices")
        else:
            context = self.retrieve(f"{crop_type} farming advisory India")

        if context:
            return f"{context}\n\n---\n\n{base_prompt}"
        return base_prompt


# Module-level singleton
_retriever: Optional[AgriRetriever] = None

def get_retriever() -> AgriRetriever:
    """Returns the module-level AgriRetriever singleton."""
    global _retriever
    if _retriever is None:
        _retriever = AgriRetriever()
    return _retriever


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    retriever = AgriRetriever()
    ctx = retriever.retrieve_for_irrigation("wheat", 22.5)
    print("=== Irrigation Context ===")
    print(ctx)
    print()
    ctx2 = retriever.retrieve_for_pest("rice", "vegetative", "pest_damage")
    print("=== Pest Context ===")
    print(ctx2)
