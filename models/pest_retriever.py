"""
models/pest_retriever.py
========================
FAISS-based retrieval of similar past pest cases and treatments.
Uses sentence-transformers "all-MiniLM-L6-v2" for lightweight local embeddings.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import List

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from models.schemas import PestCase, TreatmentPlan

log = logging.getLogger(__name__)

class PestRetriever:
    """Retrieves grounded pest knowledge using vector similarity search."""

    def __init__(
        self,
        pest_db_path: str = "configs/pest_knowledge.json",
        index_path: str = "configs/pest_faiss.index",
        embedding_dim: int = 384
    ) -> None:
        self.pest_db_path = pest_db_path
        self.index_path = index_path
        self.embedding_dim = embedding_dim
        
        # Load embedding model
        log.info("Initialising sentence-transformer: all-MiniLM-L6-v2")
        self.encoder = SentenceTransformer("all-MiniLM-L6-v2")
        
        # Load knowledge base
        if not os.path.exists(pest_db_path):
            raise FileNotFoundError(f"Pest knowledge DB not found at {pest_db_path}")
        
        with open(pest_db_path, "r") as f:
            self.pest_db = json.load(f)
            
        self.pest_names = list(self.pest_db.keys())
        log.info("Loaded pest DB with %d entries.", len(self.pest_names))
        
        # Load or build FAISS index
        if os.path.exists(index_path):
            log.info("Loading existing FAISS index from %s", index_path)
            self.index = faiss.read_index(index_path)
        else:
            log.info("FAISS index not found. Building new index...")
            self.build_index(self.pest_db)

    def build_index(self, pest_db: dict) -> None:
        """Create FAISS index from symptoms and crop metadata."""
        texts = []
        for name, data in pest_db.items():
            # Construct a rich text representation for embedding
            text = (
                f"Pest: {name}. "
                f"Symptoms: {data['symptoms']}. "
                f"Crops: {', '.join(data['affected_crops'])}. "
                f"Satellite Signature: {data.get('visual_satellite_signature', '')}"
            )
            texts.append(text)
            
        embeddings = self.encoder.encode(texts)
        
        # Initialize Flat L2 index
        self.index = faiss.IndexFlatL2(self.embedding_dim)
        self.index.add(np.array(embeddings).astype("float32"))
        
        # Save index
        faiss.write_index(self.index, self.index_path)
        log.info("FAISS index built and saved to %s (Size: %d)", self.index_path, self.index.ntotal)

    def retrieve_similar_cases(
        self,
        pest_type: str,
        crop_type: str,
        growth_stage: str,
        k: int = 3
    ) -> List[PestCase]:
        """Query FAISS index for k most similar pest cases."""
        query = f"{pest_type} on {crop_type} at {growth_stage}"
        query_embed = self.encoder.encode([query])
        
        distances, indices = self.index.search(np.array(query_embed).astype("float32"), k)
        
        results = []
        for idx in indices[0]:
            if idx == -1: continue
            pest_name = self.pest_names[idx]
            data = self.pest_db[pest_name]
            
            results.append(PestCase(
                pest_name=pest_name,
                symptoms=data["symptoms"],
                affected_crops=data["affected_crops"],
                organic_treatment=data["organic_treatment"],
                chemical_treatment=data["chemical_treatment"],
                severity_level=data["severity_level"],
                treatment_window_days=data["treatment_window_days"],
                source="pest_knowledge_db"
            ))
            
        log.info("Retrieved %d similar cases for query: %s", len(results), query)
        return results

    def get_treatment_urgency(
        self,
        pest_case: PestCase,
        affected_area_pct: float,
        urgency_level: str
    ) -> TreatmentPlan:
        """Compute priority and action timeline based on multimodal signals."""
        severity_map = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        urgency_boost = {
            "immediate": 2.0,
            "within_3_days": 1.5,
            "within_week": 1.2,
            "monitor": 1.0,
            "none": 0.8
        }
        
        base_score = severity_map.get(pest_case.severity_level.lower(), 2)
        area_multiplier = 1.0 + (affected_area_pct / 100.0)
        boost = urgency_boost.get(urgency_level.lower(), 1.0)
        
        final_score = round(base_score * area_multiplier * boost, 2)
        
        # Determine timeline
        if urgency_level == "immediate":
            hours = 24
        elif urgency_level == "within_3_days":
            hours = 72
        elif urgency_level == "within_week":
            hours = 168
        else:
            hours = 336
            
        # Strategy selection
        organic_first = pest_case.severity_level.lower() in ["low", "medium"]
        
        # Build action list
        steps = []
        if organic_first:
            steps.append(f"Primary: {pest_case.organic_treatment}")
            steps.append(f"Secondary (if persists): {pest_case.chemical_treatment}")
        else:
            steps.append(f"CRITICAL: Apply {pest_case.chemical_treatment} immediately")
            steps.append(f"Follow-up: {pest_case.organic_treatment} for residue management")
            
        # Cost estimation
        if final_score < 2.0:
            cost = "low: <500"
        elif final_score < 4.0:
            cost = "medium: 500-2000"
        else:
            cost = "high: >2000"
            
        return TreatmentPlan(
            priority_score=float(final_score),
            act_within_hours=hours,
            organic_first=organic_first,
            treatment_steps=steps,
            estimated_cost_inr=cost
        )

if __name__ == "__main__":
    # Ensure config exists for testing
    logging.basicConfig(level=logging.INFO)
    try:
        retriever = PestRetriever()
        cases = retriever.retrieve_similar_cases("aphids", "wheat", "vegetative")
        for c in cases:
            print(f"Match: {c.pest_name} (Severity: {c.severity_level})")
            plan = retriever.get_treatment_urgency(c, 15.0, "within_week")
            print(f"  Plan: {plan.priority_score} priority, act within {plan.act_within_hours}h")
    except Exception as e:
        log.error("Retriever test failed: %s", e)
